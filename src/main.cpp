#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <Arduino_Portenta_OTA.h>
#include <SensirionI2cScd4x.h>
#include <SensirionErrors.h>
#include <Arduino_PortentaMachineControl.h>
#include <sys/stat.h>
#include "secrets.h"
#include "config.h"
#include "web_ui.h"

namespace {
constexpr char LOG_PATH[]="/data/MEASUREMENTS.NDJSON", OLD_LOG_PATH[]="/data/MEASUREMENTS.OLD";
struct Measurement {
  uint32_t sequence=0, uptimeMs=0; uint16_t co2=0;
  float boxTemp=NAN, outerTemp=NAN, humidity=NAN;
  uint8_t boxFault=0, outerFault=0;
  bool co2Valid=false, boxValid=false, outerValid=false, humidityValid=false;
};
SensirionI2cScd4x scd4x; WiFiServer server(80);
Arduino_Portenta_OTA_QSPI ota(QSPI_FLASH_FATFS_MBR,2);
mbed::BlockDevice* qspiRaw=nullptr;
mbed::MBRBlockDevice* qspiData=nullptr;
mbed::FATFileSystem* qspiFs=nullptr;
mbed::MBRBlockDevice* otaData=nullptr;
mbed::FATFileSystem* otaFs=nullptr;
Measurement current, history[HISTORY_SIZE];
uint8_t historyCount=0, historyIndex=0; uint16_t scdErrors=0;
uint32_t bootId=0, lastMeasurement=0, lastSensorRetry=0, lastWifiAttempt=0;
bool sensorReady=false, storageReady=false, otaReady=false, serverStarted=false;
bool due(uint32_t n,uint32_t p,uint32_t i){return uint32_t(n-p)>=i;}
void scdError(const char* a,int16_t e){char m[96];errorToString(e,m,sizeof(m));Serial.print(a);Serial.print(": ");Serial.println(m);}
String number(float v,bool valid){return valid&&isfinite(v)?String(v,2):String("null");}
void appendRecord(String& j,const Measurement& m){
  j+="{\"boot_id\":"+String(bootId)+",\"sequence\":"+String(m.sequence)+",\"uptime_ms\":"+String(m.uptimeMs);
  j+=",\"co2\":"+(m.co2Valid?String(m.co2):String("null"));
  j+=",\"boxtemp\":"+number(m.boxTemp,m.boxValid)+",\"humidity\":"+number(m.humidity,m.humidityValid);
  j+=",\"outertemp\":"+number(m.outerTemp,m.outerValid)+",\"valid\":{\"co2\":"+String(m.co2Valid?"true":"false");
  j+=",\"boxtemp\":"+String(m.boxValid?"true":"false")+",\"humidity\":"+String(m.humidityValid?"true":"false");
  j+=",\"outertemp\":"+String(m.outerValid?"true":"false")+"},\"faults\":{\"rtd_box\":"+String(m.boxFault);
  j+=",\"rtd_outer\":"+String(m.outerFault)+"}}";
}
String apiJson(){
  String j;j.reserve(300+historyCount*210);j+="{\"firmware\":\"";j+=FIRMWARE_VERSION;j+="\",\"sensor_ready\":";
  j+=sensorReady?"true":"false";j+=",\"storage_ready\":";j+=storageReady?"true":"false";
  j+=",\"scd_errors\":"+String(scdErrors)+",\"measurement\":";appendRecord(j,current);j+=",\"history\":[";
  uint8_t first=historyCount==HISTORY_SIZE?historyIndex:0;
  for(uint8_t i=0;i<historyCount;i++){if(i)j+=',';appendRecord(j,history[(first+i)%HISTORY_SIZE]);}
  j+="]}";return j;
}
void response(WiFiClient& c,int code,const char* text,const char* type,const String& body){
  c.print("HTTP/1.1 ");c.print(code);c.print(' ');c.println(text);c.print("Content-Type: ");c.println(type);
  c.print("Content-Length: ");c.println(body.length());c.println("Cache-Control: no-store");c.println("Connection: close\r\n");c.print(body);
}
void initStorage(){
  qspiRaw=mbed::BlockDevice::get_default_instance();
  if(!qspiRaw){Serial.println("QSPI block device missing");return;}
  int rawInit=qspiRaw->init();
  if(rawInit) {Serial.print("QSPI already initialized/status: ");Serial.println(rawInit);}
  // Partition 2 is reserved for OTA. Persistent application data belongs on
  // the standard Portenta user-data partition (partition 4).
  qspiData=new mbed::MBRBlockDevice(qspiRaw,4);
  qspiFs=new mbed::FATFileSystem("data");
  int mountError=qspiFs->mount(qspiData);
  if(mountError){
    Serial.print("QSPI mount failed, formatting partition 4: ");Serial.println(mountError);
    mountError=qspiFs->reformat(qspiData);
  }
  storageReady=mountError==0;
  Serial.println(storageReady?"QSPI ready":"QSPI unavailable");
  otaData=new mbed::MBRBlockDevice(qspiRaw,2);
  otaFs=new mbed::FATFileSystem("fs");
  int otaMountError=otaFs->mount(otaData);
  if(otaMountError){
    Serial.print("OTA mount failed, formatting partition 2: ");Serial.println(otaMountError);
    otaMountError=otaFs->reformat(otaData);
  }
  otaReady=otaMountError==0;
  Serial.println(otaReady?"OTA ready":"OTA unavailable");
}
uint32_t nextBootId(){
  uint32_t id=0;
  if(storageReady){
    FILE* f=fopen("/data/BOOT.ID","rb");
    if(f){fread(&id,sizeof(id),1,f);fclose(f);}
    id++;
    f=fopen("/data/BOOT.ID","wb");
    if(f){fwrite(&id,sizeof(id),1,f);fflush(f);fclose(f);}
  }
  return id ? id : (uint32_t(micros()) ^ 0xA5C3417D);
}
void persist(const Measurement& m){
  if(!storageReady)return;
  struct stat s{};
  if(!stat(LOG_PATH,&s)&&size_t(s.st_size)>=PERSISTENT_LOG_MAX_BYTES){remove(OLD_LOG_PATH);rename(LOG_PATH,OLD_LOG_PATH);}
  FILE* f=fopen(LOG_PATH,"a");if(!f){storageReady=false;return;}
  String line;line.reserve(220);appendRecord(line,m);line+='\n';
  if(fwrite(line.c_str(),1,line.length(),f)!=line.length())storageReady=false;
  fflush(f);fclose(f);
}
bool initScd(TwoWire& bus,const char* name){
  bus.begin();bus.setClock(100000);scd4x.begin(bus,SCD41_I2C_ADDR_62);scd4x.wakeUp();delay(35);
  scd4x.stopPeriodicMeasurement();delay(500);uint64_t serial;int16_t e=scd4x.getSerialNumber(serial);if(e)return false;
  if((e=scd4x.setTemperatureOffset(SCD41_TEMPERATURE_OFFSET_C)))scdError("offset",e);
  if((e=scd4x.setSensorAltitude(SCD41_ALTITUDE_M)))scdError("altitude",e);
  if((e=scd4x.setAutomaticSelfCalibrationEnabled(SCD41_ASC_ENABLED)))scdError("ASC",e);
  if((e=scd4x.startPeriodicMeasurement()))return false;
  scdErrors=0;Serial.print("SCD4x: ");Serial.println(name);return true;
}
void initSensors(){sensorReady=initScd(Wire,"Wire")||initScd(Wire1,"Wire1");}
void readRtd(uint8_t ch,float& v,bool& valid,uint8_t& fault){
  MachineControl_RTDTempProbe.selectChannel(ch);v=MachineControl_RTDTempProbe.readTemperature(RTD_NOMINAL_OHMS,RTD_REFERENCE_OHMS);
  fault=MachineControl_RTDTempProbe.readFault();valid=!fault&&isfinite(v)&&v>=-100&&v<=200;
  if(fault)MachineControl_RTDTempProbe.clearFault();
  if(!valid)v=NAN;
}
void acquire(uint32_t now){
  Measurement n;n.sequence=current.sequence+1;n.uptimeMs=now;
  if(sensorReady){bool ready=false;int16_t e=scd4x.getDataReadyStatus(ready);float ignored;
    if(!e&&ready)e=scd4x.readMeasurement(n.co2,ignored,n.humidity);
    if(e){scdError("read",e);if(++scdErrors>=3)sensorReady=false;}
    else if(ready&&n.co2){n.co2Valid=true;n.humidityValid=isfinite(n.humidity)&&n.humidity>=0&&n.humidity<=100;scdErrors=0;}
  }
  readRtd(RTD_BOX_CHANNEL,n.boxTemp,n.boxValid,n.boxFault);readRtd(RTD_OUTER_CHANNEL,n.outerTemp,n.outerValid,n.outerFault);
  current=n;history[historyIndex]=n;historyIndex=(historyIndex+1)%HISTORY_SIZE;if(historyCount<HISTORY_SIZE)historyCount++;persist(n);
  Serial.print("#");Serial.print(n.sequence);Serial.print(" CO2=");n.co2Valid?Serial.print(n.co2):Serial.print("invalid");
  Serial.print(" box=");n.boxValid?Serial.print(n.boxTemp):Serial.print("invalid");Serial.print(" outer=");n.outerValid?Serial.println(n.outerTemp):Serial.println("invalid");
}
void wifi(uint32_t now){
  if(WiFi.status()==WL_CONNECTED){if(!serverStarted){server.begin();serverStarted=true;Serial.println(WiFi.localIP());}return;}
  serverStarted=false;if(due(now,lastWifiAttempt,WIFI_RECONNECT_INTERVAL_MS)){lastWifiAttempt=now;WiFi.begin(WIFI_SSID,WIFI_PASSWORD);}
}
bool headers(WiFiClient& c,String& request,String& h){
  uint32_t start=millis();while(c.connected()&&!due(millis(),start,2000)){if(!c.available()){delay(1);continue;}request=c.readStringUntil('\n');break;}
  while(c.connected()&&!due(millis(),start,2000)){if(!c.available()){delay(1);continue;}String l=c.readStringUntil('\n');if(l=="\r")return true;h+=l;h+='\n';if(h.length()>4096)return false;}return false;
}
int contentLength(const String& h){int p=h.indexOf("Content-Length:");return p<0?-1:h.substring(p+15).toInt();}
String boundary(const String& h){
  int p=h.indexOf("boundary=");if(p<0)return "";String b=h.substring(p+9);int e=b.indexOf('\r');if(e>=0)b=b.substring(0,e);
  e=b.indexOf('\n');if(e>=0)b=b.substring(0,e);b.trim();if(b.startsWith("\"")&&b.endsWith("\""))b=b.substring(1,b.length()-1);return "--"+b;
}
void upload(WiFiClient& c,int length,const String& b){
  if(!otaReady||length<=0||b.length()<3){response(c,400,"Bad Request","text/plain","Invalid OTA request.");return;}
  FILE* f=fopen("/fs/UPDATE.BIN.LZSS","wb");if(!f){response(c,500,"Error","text/plain","Cannot open OTA file.");return;}
  String ph;bool data=false,failed=false;int received=0,written=0,expectedFileSize=-1;uint8_t prefix[4]={0};uint8_t prefixCount=0;uint32_t last=millis();uint8_t buf[512];
  while(received<length&&c.connected()&&!due(millis(),last,5000)){if(!c.available()){delay(1);continue;}last=millis();
    if(!data){char x=c.read();received++;ph+=x;if(ph.endsWith("\r\n\r\n"))data=true;if(ph.length()>2048){failed=true;break;}continue;}
    int count=min(min(c.available(),int(sizeof(buf))),length-received),got=c.read(buf,count);
    if(got>0){received+=got;
      for(int i=0;i<got&&prefixCount<4;i++)prefix[prefixCount++]=buf[i];
      if(prefixCount==4&&expectedFileSize<0){uint32_t payload=uint32_t(prefix[0])|(uint32_t(prefix[1])<<8)|(uint32_t(prefix[2])<<16)|(uint32_t(prefix[3])<<24);expectedFileSize=int(payload+8);}
      int toWrite=got;if(expectedFileSize>=0)toWrite=min(toWrite,max(0,expectedFileSize-written));
      if(toWrite&&fwrite(buf,1,toWrite,f)!=size_t(toWrite)){failed=true;break;}written+=toWrite;
    }
  }
  if(received!=length||failed||expectedFileSize<=8||written!=expectedFileSize)failed=true;
  fclose(f);
  if(failed){remove("/fs/UPDATE.BIN.LZSS");response(c,400,"Bad Request","text/plain","Incomplete OTA upload.");return;}
  int decompressed=ota.decompress();
  if(decompressed<0){response(c,422,"Invalid","text/plain","OTA decompression failed: "+String(decompressed));return;}
  Arduino_Portenta_OTA::Error updateError=ota.update();
  if(updateError!=Arduino_Portenta_OTA::Error::None){response(c,422,"Invalid","text/plain","OTA activation failed: "+String(static_cast<int>(updateError)));return;}
  response(c,200,"OK","text/plain","OTA verified; restarting.");delay(500);c.stop();ota.reset();
}
void stream(WiFiClient& c,const char* path){FILE* f=fopen(path,"r");if(!f)return;uint8_t b[512];size_t n;while((n=fread(b,1,sizeof(b),f))&&c.connected())c.write(b,n);fclose(f);}
void backlog(WiFiClient& c){c.println("HTTP/1.1 200 OK");c.println("Content-Type: application/x-ndjson");c.println("Connection: close\r\n");if(storageReady){stream(c,OLD_LOG_PATH);stream(c,LOG_PATH);}}
void client(){
  WiFiClient c=server.accept();if(!c)return;String r,h;r.reserve(128);h.reserve(1024);
  if(!headers(c,r,h))response(c,400,"Bad Request","text/plain","Malformed request.");
  else if(r.startsWith("GET /api/measurement"))response(c,200,"OK","application/json",apiJson());
  else if(r.startsWith("GET /api/backlog"))backlog(c);
  else if(r.startsWith("GET /update"))response(c,200,"OK","text/html; charset=utf-8",UPDATE_HTML);
  else if(r.startsWith("POST /update")){upload(c,contentLength(h),boundary(h));return;}
  else if(r.startsWith("GET / ")||r.startsWith("GET /index.html"))response(c,200,"OK","text/html; charset=utf-8",INDEX_HTML);
  else response(c,404,"Not Found","text/plain","Not found.");
  delay(1);c.stop();
}
}
void setup(){
  Serial.begin(115200);uint32_t start=millis();while(!Serial&&!due(millis(),start,2000))delay(10);
  MachineControl_RTDTempProbe.begin(THREE_WIRE);
  Serial.print("RTD box=");Serial.print(RTD_BOX_CHANNEL);Serial.print(" outer=");Serial.println(RTD_OUTER_CHANNEL);
  initStorage();bootId=nextBootId();initSensors();WiFi.begin(WIFI_SSID,WIFI_PASSWORD);lastWifiAttempt=millis();lastMeasurement=millis()-MEASUREMENT_INTERVAL_MS;
}
void loop(){
  uint32_t now=millis();wifi(now);
  if(!sensorReady&&due(now,lastSensorRetry,SENSOR_RETRY_INTERVAL_MS)){lastSensorRetry=now;initSensors();}
  if(due(now,lastMeasurement,MEASUREMENT_INTERVAL_MS)){lastMeasurement+=MEASUREMENT_INTERVAL_MS;if(due(now,lastMeasurement,MEASUREMENT_INTERVAL_MS))lastMeasurement=now;acquire(now);}
  if(serverStarted)client();
}
