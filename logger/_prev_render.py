import matplotlib; matplotlib.use('Agg')
import sys; sys.path.insert(0, r'C:\Users\michi\git\fastnchip-sensors\logger')
# monkey-patch plt.show so it saves instead
import matplotlib.pyplot as _plt
_orig_show = _plt.show
def _save(): 
    import matplotlib.pyplot as plt
    plt.savefig(r'C:\Users\michi\git\fastnchip-sensors\logger\_prev.png', dpi=120, bbox_inches='tight')
    print('saved')
_plt.show = _save

import viewer; viewer.main()
