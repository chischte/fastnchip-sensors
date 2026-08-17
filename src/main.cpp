#include <Arduino.h>
#include <Wire.h>
#include <SensirionI2cScd4x.h>

SensirionI2cScd4x scd4x;

void printMeasurementError(uint16_t error) {
  Serial.print("SCD4x error: ");
  Serial.println(error);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(10);
  }

  Wire.begin();

  Serial.println("Initializing SCD4x...");

  scd4x.begin(Wire, SCD41_I2C_ADDR_62);

  uint16_t error = scd4x.startPeriodicMeasurement();
  if (error) {
    printMeasurementError(error);
    Serial.println("Check the I2C wiring and sensor power.");
    while (1) {
      delay(1000);
    }
  }

  Serial.println("Waiting for SCD4x measurement...");
  delay(5000);

  error = scd4x.stopPeriodicMeasurement();
  if (error) {
    printMeasurementError(error);
  }

  error = scd4x.startPeriodicMeasurement();
  if (error) {
    printMeasurementError(error);
  }

  Serial.println("Waiting for SCD4x measurement...");
  delay(5000);
}

void loop() {
  uint16_t error;
  uint16_t co2 = 0;
  float temperature = 0.0f;
  float humidity = 0.0f;

  error = scd4x.readMeasurement(co2, temperature, humidity);
  if (error) {
    printMeasurementError(error);
    delay(1000);
    return;
  }

  if (co2 == 0) {
    Serial.println("No measurement available yet.");
    delay(1000);
    return;
  }

  Serial.print("CO2: ");
  Serial.print(co2);
  Serial.print(" ppm | Temperature: ");
  Serial.print(temperature, 2);
  Serial.print(" C | Humidity: ");
  Serial.print(humidity, 2);
  Serial.println(" %RH");

  delay(5000);
}
