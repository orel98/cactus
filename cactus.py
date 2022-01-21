#!/usr/bin/python
import os
from pickle import TUPLE
from typing import Tuple
import paramiko
import socket
import hashlib
import sys
import json
import argparse

from paramiko import SFTPClient


# Checks if desired port is responding
def ping_via_ssh_port(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    try:
        s.connect((host, port))
        s.shutdown(socket.SHUT_WR)
        data = s.recv(512)
        s.close()
        if not data:
            return False
        print("ssh ping ok..")
        return True
    except socket.timeout:
        return False


# Hash function
def sha1_files(filename: str) -> str:
    sha1 = hashlib.sha1()

    # We don't want to push huge file into our memory but we need to hash all the file content
    # so we divide it into chunks of 128 * 1024 bytes ~ 130k
    ba = bytearray(128 * 1024)
    mv = memoryview(ba)
    with open(filename, "rb", buffering=0) as f:
        for chunk in iter(lambda: f.readinto(mv), 0):
            sha1.update(mv[:chunk])

    return sha1.hexdigest()


def update_dict(path: str, server_path: str) -> dict:
    hashes_files = {}
    for root, _dirs, files in os.walk(path):
        for file in files:
            file = os.path.join(root, file)
            hashes_files[sha1_files(file)] = file
    print("scanning local files..")
    with open("cactus.temp.txt", "w") as f:
        f.write(f"{server_path}\n")
        for key, val in hashes_files.items():
            f.write(key + "$" + val + "\n")
    return hashes_files


# Getting the folder structure, we will need this in case the folder structure on the server don't match
def get_folder_struct(path: str) -> None:
    with open("cactus.temp.txt", "a") as f:
        for root, folders_name, _ in os.walk(path):
            for folder in folders_name:
                folder = os.path.join(root, folder)
                folder = folder.lstrip(path)
                f.write(folder + "\n")


# hashing all the file in the destination (one by one), in order to compate them to the files on the client,
# we want to copy only the files that changed or doesn't exists on the server
def get_remote_hashes(
    ip: str, username: str, key: str, port: int, server_path: str
) -> Tuple(dict, SFTPClient):

    remote_dict = {}
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(ip, port, username, key_filename=key, timeout=5)

    except paramiko.SSHException:
        exit(1)
    print("ssh connection established!")
    sftp = client.open_sftp()
    try:
        sftp.put("cactus.temp.txt", server_path + "cactus.temp.txt")
        sftp.put("to_run_on_server.py", server_path + "cactus.temp.py")
    except FileNotFoundError:
        client.exec_command(f"mkdir -p {server_path}")
        sftp.put("cactus.temp.txt", server_path + "cactus.temp.txt")
        sftp.put("to_run_on_server.py", server_path + "cactus.temp.py")

    client.exec_command(f"cd {server_path}")
    print("geting remote hashes..")
    _, Out, _ = client.exec_command(f"cd {server_path} && python3 cactus.temp.py")

    for line in Out.readlines():
        split = line.split("$")
        remote_dict[split[0]] = split[1]

    return remote_dict, sftp


# callback function for "sftp_client.put"
def progress(sent: int, to_sent: int) -> None:
    global total_files_size, totalsent, allready_sent
    totalsent += sent - allready_sent
    allready_sent = sent if sent / to_sent != 1 else 0
    sys.stdout.write(
        "progress: %.2f%% \r" % (float(totalsent / total_files_size) * 100)
    )
    # sys.stdout.flush()


def args() -> dict[str]:
    args_dict = {}
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-e",
        "--edit_conf",
        help="opens cactos.conf.json to edit manualy",
        action="store_true",
    )
    args = parser.parse_args()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--use_saved_conf",
        help="use defualt seved in : cactus.conf.json, (need to be in cactus directory).",
        action="store_true",
    )
    args = parser.parse_args()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--set_ip",
        help="set new ip and keep rest of paramaters in cactus.conf.json file",
        action="store_true",
    )
    args = parser.parse_args()

    args_dict["edit_conf"] = args.edit_conf
    args_dict["set_ip"] = args.set_ip
    args_dict["use_saved_conf"] = args.use_saved_conf

    return args_dict


def manual_paramters(OS):
    if OS == "posix":
        key = os.path.expanduser("~") + "/.ssh/id_rsa.pub"

    elif OS == "nt":
        key = "%SystemDrive%/Users/%UserName%/.ssh/id_rsa.pub"
    else:
        print("os not suported, aborting")
        exit(-1)

    HOSTNAME = input("Hostname (or IP): ")
    PORT = None
    while PORT is not int:
        try:
            PORT = int(input("Port (defualt 22): "))
            break
        except ValueError:
            print("only numbers pls..")
    USERNAME = input("User name: ")
    KEY = input(f"Path to ssh poublic key (defult is {key}: )")
    if not KEY:
        KEY = key
    CLIENT_PATH = input("Directory path to backup: ")
    CLIENT_PATH += "/" if not CLIENT_PATH.endswith("/") else ""
    CLIENT_PATH = "/" + CLIENT_PATH if not CLIENT_PATH.startswith("/") else CLIENT_PATH
    SERVER_PATH = input("Path to backup directory on the server: ")
    SERVER_PATH += "/" if not SERVER_PATH.endswith("/") else ""
    SERVER_PATH = "/" + SERVER_PATH if not SERVER_PATH.startswith("/") else SERVER_PATH

    save_to_next_time = input(
        "do you wish to save configuration to next time? [y/N]: "
    ).upper()
    if save_to_next_time == "Y":
        with open("cactus.conf.json", "w", encoding="utf-8") as jfile:
            data = {}
            data["conf"] = {}
            (
                data["conf"]["hostname"],
                data["conf"]["port"],
                data["conf"]["username"],
                data["conf"]["sshKeyPath"],
                data["conf"]["clientDirectory"],
                data["conf"]["serverDirectory"],
            ) = (HOSTNAME, PORT, USERNAME, KEY, CLIENT_PATH, SERVER_PATH)
            jfile.seek(0)
            json.dump(data, jfile, ensure_ascii=False, indent=4)
            jfile.truncate()
        print("Saved.")
    return HOSTNAME, PORT, USERNAME, KEY, CLIENT_PATH, SERVER_PATH


if __name__ == "__main__":
    OS = os.name
    args_dict = args()
    if args_dict["set_ip"]:
        if "cactus.conf.json" in os.listdir(os.getcwd()):
            with open("cactus.conf.json", "r") as f:
                conf = json.load(f)
                conf["conf"]["hostname"] = input("IP: ")

    if args_dict["use_defualts"]():
        if "cactus.conf.json" in os.listdir(os.getcwd()):
            with open("cactus.conf.json", "r") as f:
                conf = json.load(f)
            (HOSTNAME, PORT, USERNAME, KEY, CLIENT_PATH, SERVER_PATH) = (
                conf["conf"]["hostname"],
                conf["conf"]["port"],
                conf["conf"]["username"],
                conf["conf"]["sshKeyPath"],
                conf["conf"]["clientDirectory"],
                conf["conf"]["serverDirectory"],
            )
        else:
            answer = input(
                "Cant find configuration files.. do you want to enter configuration manualy? [y/N]"
            ).upper()
            if answer == "Y":
                (
                    HOSTNAME,
                    PORT,
                    USERNAME,
                    KEY,
                    CLIENT_PATH,
                    SERVER_PATH,
                ) = manual_paramters(OS)
            else:
                exit(0)

    else:
        (HOSTNAME, PORT, USERNAME, KEY, CLIENT_PATH, SERVER_PATH) = manual_paramters(OS)

    if ping_via_ssh_port(HOSTNAME, PORT):
        client_dict = update_dict(CLIENT_PATH, SERVER_PATH)
        get_folder_struct(CLIENT_PATH)
        server_dict, sftp_client = get_remote_hashes(
            HOSTNAME, USERNAME, KEY, PORT, SERVER_PATH
        )
        total_files_size = sum(
            [
                os.stat(client_dict[i]).st_size
                for i in client_dict
                if i not in server_dict
            ]
        )
        totalsent, allready_sent = 0, 0
        print("copying files...")
        files_count = 0
        for i in client_dict:
            if i not in server_dict:
                sftp_client.put(
                    client_dict[i],
                    SERVER_PATH + (client_dict[i].lstrip(CLIENT_PATH)),
                    callback=progress,
                )
                files_count += 1

        os.remove("cactus.temp.txt")
        sftp_client.close
        print(f"done! {files_count} files moved.")
    else:
        print("cant ping the server, aborting..")
        exit(-1)
