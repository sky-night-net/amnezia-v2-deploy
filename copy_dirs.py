import shutil
import os

src_base = '/Users/sky_night/Projects/Amnezia_VPN_Project/'
dst_base = '/Users/sky_night/Projects/amnezia-v2-deploy/'

dirs_to_copy = [
    'Automator_App',
    'Amnezia_Premium_Dashboard'
]

for d in dirs_to_copy:
    src_path = os.path.join(src_base, d)
    dst_path = os.path.join(dst_base, d)
    if os.path.exists(dst_path):
        shutil.rmtree(dst_path)
    print(f"Copying tree {src_path} to {dst_path}")
    shutil.copytree(src_path, dst_path)

print("Directory copy complete")
