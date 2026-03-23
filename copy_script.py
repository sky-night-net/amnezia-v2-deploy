import shutil
import os

src = '/Users/sky_night/Projects/Amnezia_VPN_Project/'
dst = '/Users/sky_night/Projects/amnezia-v2-deploy/'

files = [
    'amnezia-cli.py',
    'amnezia-deploy.py',
    'requirements.txt'
]

for f in files:
    print(f"Copying {f}")
    shutil.copy2(os.path.join(src, f), os.path.join(dst, f))

os.makedirs(os.path.join(dst, "stats"), exist_ok=True)
shutil.copy2(os.path.join(src, "statsCollector_native.py"), os.path.join(dst, "stats/statsCollector_native.py"))
print("Done copying")
