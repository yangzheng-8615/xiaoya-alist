#!/usr/local/bin/python3

import json
import base64
import requests
import time
import logging
import os
import threading
import sys
import qrcode
import argparse
from PIL import Image
import pyzbar.pyzbar as pyzbar
from io import BytesIO
from flask import Flask, send_file, render_template, jsonify


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
last_status = 0
if sys.platform.startswith('win32'):
    qrcode_dir = 'qrcode.png'
else:
    qrcode_dir= '/aliyuntoken/qrcode.png'


def poll_qrcode_status(data, log_print):
    global last_status
    while True:
        re = requests.post('https://api-cf.nn.ci/alist/ali/ck', json=data)
        if re.status_code == 200:
            re_data = json.loads(re.text)
            if re_data['content']['data']['qrCodeStatus'] == 'CONFIRMED':
                h = re_data['content']['data']['bizExt']
                c = json.loads(base64.b64decode(h).decode('gbk'))
                refresh_token = c['pds_login_result']['refreshToken']
                if sys.platform.startswith('win32'):
                    with open('mytoken.txt', 'w') as f:
                        f.write(refresh_token)
                else:
                    with open('/data/mytoken.txt', 'w') as f:
                        f.write(refresh_token)
                logging.info('扫码成功, refresh_token 已写入文件！')
                last_status = 1
                break
            else:
                if log_print:
                    logging.info('等待用户扫码...')
                time.sleep(2)


def decode_qr_code(qr_code_image_path):
    img = Image.open(qr_code_image_path)
    decoded_objects = pyzbar.decode(img)
    for obj in decoded_objects:
        return obj.data.decode('utf-8')


@app.route("/")
def index():
    return render_template('index.html')


@app.route('/image')
def serve_image():
    return send_file(qrcode_dir, mimetype='image/png')


@app.route('/status')
def status():
    if last_status == 1:
        return jsonify({'status': 'success'})
    elif last_status == 2:
        return jsonify({'status': 'failure'})
    else:
        return jsonify({'status': 'unknown'})


@app.route('/shutdown_server', methods=['GET'])
def shutdown():
    if os.path.isfile(qrcode_dir):
        os.remove(qrcode_dir)
    os._exit(0)


if __name__ == '__main__':
    if os.path.isfile(qrcode_dir):
        os.remove(qrcode_dir)
    parser = argparse.ArgumentParser(description='AliyunPan Refresh Token')
    parser.add_argument('--qrcode_mode', type=str, help='扫码模式')
    args = parser.parse_args()
    logging.info('二维码生成中...')
    re_count = 0
    while True:
        re = requests.get('https://api-cf.nn.ci/alist/ali/qr')
        if re.status_code == 200:
            re_data = json.loads(re.content)
            t = str(re_data['content']['data']['t'])
            codeContent = re_data['content']['data']['codeContent']
            ck = re_data['content']['data']['ck']
            url = f"https://api-cf.nn.ci/qr/?size=400&text={codeContent}"
            re = requests.get(url)
            if re.status_code == 200:
                image_stream = BytesIO(re.content)
                image = Image.open(image_stream)
                image.save(qrcode_dir)
                data = {"ck": ck, "t": t}
                if os.path.isfile(qrcode_dir):
                    logging.info('二维码生成完成！')
                    break
        time.sleep(1)
        re_count += 1
        if re_count == 3:
            logging.error('二维码生成失败，退出进程')
            os._exit(1)
    if args.qrcode_mode == 'web':
        threading.Thread(target=poll_qrcode_status, args=(data, True)).start()
        app.run(host='0.0.0.0', port=34256)
    elif args.qrcode_mode == 'shell':
        threading.Thread(target=poll_qrcode_status, args=(data, False)).start()
        decoded_data = decode_qr_code(qrcode_dir)
        qr = qrcode.QRCode(border=1)
        qr.add_data(decoded_data)
        qr.make(fit=True)
        qr.make_image(fill_color="black", back_color="white")
        qr.print_ascii(invert=True, tty=sys.stdout.isatty())
        while last_status != 1:
            time.sleep(1)
        if os.path.isfile(qrcode_dir):
            os.remove(qrcode_dir)
        os._exit(0)
    else:
        logging.error('未知的扫码模式')
        os._exit(1)
