import requests
import sys
import time
import sqlite3
import re
import os
import json
import random
import schedule
import getopt
from loguru import logger

ua = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.2832.1 Safari/537.36'
error_count = 0
device_id = ''
global live_dic
create_table = '''CREATE TABLE IF NOT EXISTS livelist (
    liveID TEXT PRIMARY KEY,
uid INTEGER NOT NULL,
name TEXT NOT NULL,
startTime TEXT NOT NULL,
title TEXT NOT NULL,
iKaURL TEXT NOT NULL,
iKaCutId INTEGER NOT NULL DEFAULT 0
);
'''
create_err_table = '''CREATE TABLE IF NOT EXISTS getIKarCutErrList (
    liveID TEXT PRIMARY KEY,
uid INTEGER NOT NULL
);
'''
insert_err = '''
INSERT OR IGNORE INTO getIKarCutErrList (liveID,uid) VALUES (?,?)
'''
delete_err = '''
DELETE FROM getIKarCutErrList WHERE liveID = ?
'''
insert_rec = '''INSERT OR IGNORE INTO livelist
(liveID, uid, name, startTime, title, iKaURL, iKaCutId)
VALUES
(?, ?, ?, ?, ?, ?, ?);'''
select_live_id = 'SELECT COUNT(1) AS count FROM livelist WHERE liveID = ?'
DEFAULT_JSON = {"targe_uid": [], "interval": 1}
headers = {}
connect_retry_time = 0
def acfunRequest(url):
    global connect_retry_time
    try:
        ret = requests.get(url, headers=headers)
        connect_retry_time = 0
        return ret
    except Exception:
        return None


def get_live_list(page):
    global error_count
    logger.info('正在获取第%d页数据' % (page + 1))
    url = 'https://live.acfun.cn/api/channel/list?count=100&pcursor={}'.format(page)
    ret = acfunRequest(url)
    if ret == None:
        logger.error('连接网络错误，重试中')
        time.sleep(5)
        get_live_list(page)
    else:
        if ret.status_code == 200:
            r_json = ret.json()
            if 'isError' in r_json:
                error_count += 1
                if error_count < 3:
                    logger.error('获取失败，重试中...%d' % error_count)
                    acfunRequest(url)
                else:
                    logger.error('获取失败，退出程序')
                    sys.exit()
            else:
                error_count = 0
                list_len = len(r_json['liveList'])
                total = r_json['totalCount']
                if page > 0:
                    cur_get_count = (page + 1) * 100 + list_len
                else:
                    cur_get_count = list_len
                for i in range(0, list_len):
                    l = r_json['liveList'][i]
                    time_local = time.localtime(l['createTime'] / 1000)
                    dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
                    liver = l['user']['name']
                    live_dic[str(l['authorId'])] = {'authorName': liver, 'liveId': l['liveId'], 'title': l['title'],
                                                    'startLiveTime': dt}
                if cur_get_count < total:
                    return True
                else:
                    logger.info('数据获取完成')
                    logger.info('%d个正在直播' % total)
                    return False
        else:
            logger.error('error：%d' % ret.status_code)
            return False


def generate_did(code_len=16):
    all_char = '0123456789ABCDEF'
    index = len(all_char) - 1
    code = ''
    for _ in range(code_len):
        num = random.randint(0, index)
        code += all_char[num]
    return code


def get_ika_cut_id(author_id):
    if author_id in live_dic:
        live_id = live_dic[author_id]['liveId']
        s_res = cur.execute(select_live_id, (live_id,))
        if s_res.fetchone()[0] == 0:
            url = 'https://live.acfun.cn/rest/pc-direct/live/getLiveCutInfo?authorId={}&liveId={}'.format(author_id,
                                                                                                          live_id)
            res = acfunRequest(url)
            try_time = 0
            if res == None:
                if try_time < 3:
                    try_time += 1
                    print('获取爱咔链接失败，正在重试：%d' % try_time)
                    get_ika_cut_id(author_id)
                else:
                    cur.execute(insert_err, (live_id, int(author_id)))
                    conn.commit()
                    logger.error('获取爱咔链接失败，主包id:{}，直播id: {}'.format(author_id, live_id))
            else:
                save_ika_data(res, author_id, live_id)
    else:
        logger.info('主包(%s)未开播' % author_id)

def get_ika_cut_id_for_err(author_id, live_id):
    url = 'https://live.acfun.cn/rest/pc-direct/live/getLiveCutInfo?authorId={}&liveId={}'.format(author_id,
                                                                                                  live_id)
    res = acfunRequest(url)
    try_time = 0
    if res == None:
        if try_time < 3:
            try_time += 1
            print('获取爱咔链接失败，正在重试：%d' % try_time)
            get_ika_cut_id_for_err(author_id, live_id)
        else:
            logger.error('获取爱咔链接失败，主包id:{}，直播id: {}'.format(author_id, live_id))
    else:
        save_ika_data(res, author_id, live_id, is_err_save_opt=True)



def save_ika_data(res, author_id,live_id ,is_err_save_opt = False):
    r_json = res.json()
    authorName = live_dic[author_id]['authorName']
    try:
        iKaUrl = r_json['liveCutUrl']
        iKaCutId = int(re.findall('[0-9]+', iKaUrl)[0])
    except KeyError:
        iKaUrl = '该主包未开启爱咔录像权限'
        iKaCutId = 0
    title = live_dic[author_id]['title']
    startLiveTime = live_dic[author_id]['startLiveTime']
    uid = int(author_id)
    cur.execute(insert_rec, (live_id, uid, authorName, startLiveTime, title, iKaUrl, iKaCutId))
    conn.commit()
    if is_err_save_opt:
        cur.execute(delete_err, (live_id,))
        conn.commit()
    logger.info('主包直播id：%s（%s），录播爱咔链接：%s' % (live_id, authorName, iKaUrl))

def get_config():
    config_path = os.getcwd() + '/config.json'
    try:
        with open(config_path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            with open(file=config_path, mode="w+", encoding='utf-8') as file:
                json.dump(DEFAULT_JSON, file)
                sys.exit(0)
        except Exception:
            sys.exit(1)


def get_ika_id_task():
    global live_dic
    live_dic = dict()
    flag = True
    page = 0
    while flag:
        flag = get_live_list(page)
        page += 1
    if len(targe_liver) == 0:
        for uid in live_dic:
            get_ika_cut_id(uid)
    else:
        for t in targe_liver:
            get_ika_cut_id(t)


if __name__ == '__main__':
    list_mode = False
    get_err_data_mode = False
    out_put_file_name = 'out.txt'
    try:
        opts, args = getopt.getopt(sys.argv[1:], "-h-f-q-l:", ['help', 'filename=', 'query-err', 'list'])
        for opt_name, opt_value in opts:
            if opt_name in ('-h', '--help'):
                print("[*] Help info")
                print(
                    "[*] 使用-l或--list参数可以查询已保存的爱咔录播回放记录，可通过添加-f或--filename参数指定查询后输出的txt文件名")
                print(
                    "[*] 使用-q或--query-err参数可以重新查询获取失败的数据")
                exit()
            if opt_name in ('-q', '--query-err'):
                get_err_data_mode = True
            if opt_name in ('-l', '--list'):
                list_mode = True
            if opt_name in ('-f', '--filename'):
                out_put_file_name = opt_value
    except getopt.GetoptError:
        pass
    if list_mode:
        with sqlite3.connect('liveika.db') as conn:
            cur = conn.cursor()
            query_sql = '''
            SELECT liveId,uid,name,startTime,title,iKaURL,iKaCutId from livelist where iKaCutId != 0
            '''
            res = cur.execute(query_sql).fetchall()
            if len(res) != 0:
                p_str = ''
                for row in res:
                    live_id = row[0]
                    uid = row[1]
                    name = row[2]
                    start_time = row[3]
                    title = row[4]
                    ika_url = row[5]
                    ika_cut_id = row[6]
                    p_str = p_str+'主播：%s（%d），直播标题：%s，爱咔链接：%s，爱咔录播id：%d，开播时间：%s\n' % (
                        name, uid, title, ika_url, ika_cut_id, start_time)
                    print('主播：%s（%d），直播标题：%s，爱咔链接：%s，爱咔录播id：%d，开播时间：%s' % (
                    name, uid, title, ika_url, ika_cut_id, start_time))
                with open(out_put_file_name, "w", encoding='utf-8') as file:
                    file.write(p_str)
                    print('结果已导出到：%s' % out_put_file_name)
            else:
                print('数据库中没有数据')
                exit()
    else:
        if get_err_data_mode:
            with sqlite3.connect('liveika.db') as conn:
                cur = conn.cursor()
                query_sql = '''
                SELECT liveID,uid from getIKarCutErrList
                '''
                res = cur.execute(query_sql).fetchall()
                if len(res) != 0:
                    for row in res:
                        live_id = row[0]
                        uid = row[1]
                        get_ika_cut_id_for_err(uid, live_id)
                else:
                    logger.info('暂无获取失败的数据')
        else:
            headers = {
                'User-Agent': ua,
                'Accept-Encoding': 'gzip',
                'cookie': '_did=web_' + device_id
            }

            data = get_config()
            conn = sqlite3.connect('liveika.db')
            cur = conn.cursor()
            cur.execute(create_table)
            cur.execute(create_err_table)
            conn.commit()
            device_id = generate_did()
            try:
                targe_liver = data['targe_uid']
            except KeyError:
                targe_liver = []
            try:
                interval = data['interval']
            except KeyError:
                interval = 1
            if interval < 1:
                interval = 1
            get_ika_id_task()
            schedule.clear()
            schedule.every(interval).minutes.do(get_ika_id_task)
            while True:
                schedule.run_pending()
                time.sleep(1)
