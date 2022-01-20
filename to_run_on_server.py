import os
import hashlib

def get_folder_struct():
    with open("cactus.temp.txt", 'r') as f:
        l = f.readlines()
        path = l[0].rstrip()
        for i in l[1:]:
            i = i.rstrip()
            if "$" not in i and not os.path.isdir(i):
                os.makedirs(i, exist_ok=True)   #makdir -p     
    return path

def sha1_files(filename):
    sha1 = hashlib.sha1()
    ba = bytearray(128*1024)
    mv = memoryview(ba)
    with open(filename, 'rb', buffering=0) as f:
        for chunk in iter(lambda : f.readinto(mv), 0):
            sha1.update(mv[:chunk])
    return sha1.hexdigest()

def update_dict(path):
    hashes_files = {}
    for root, _dirs, files in os.walk(path):
        for file in files:
            file = os.path.join(root, file)
            hashes_files[sha1_files(file)] = file
    for key, val in hashes_files.items():
        print(key+"$"+val)


if __name__ == "__main__":
    path = get_folder_struct()
    update_dict(path)
    os.remove(__file__)
    os.remove("cactus.temp.txt")






    
