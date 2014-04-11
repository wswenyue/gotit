#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import datetime
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import web
from web import ctx
from web.contrib.template import render_jinja

#import redis
from bson import ObjectId
from weibo import APIClient, APIError

from addons import mongo2s
from addons.redis2s import rds
from addons.utils import zipf2strio

render = render_jinja('templates', encoding='utf-8')


APP_KEY = rds.get('weibo_app_key') # app key
APP_SECRET = rds.get('weibo_app_secret') # app secret
CALLBACK_URL = 'http://gotit.asia/manage/callback' # callback url
CLIENT = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=CALLBACK_URL)
AUTH_URL=CLIENT.get_authorize_url()

ADMIN_WEIBO_ID = int(rds.get('admin_weibo_id'))

# init mongoDB
db = mongo2s.init_mongo()

urls = (
    '$', 'ologin',
    '/callback', 'callback',
    '/panel', 'panel',
    '/now', 'now',
    '/analytics', 'analytics',

    '/backup/(.+)', 'backup',
    '/backup', 'backup',

    '/readlog/(.+)', 'readlog',

    '/o/(.+)/(.+)/(.+)', 'update',
    '/o/(.+)/(.+)', 'update',

    '/de/(.+)/(.+)/(.+)', 'DetailError',
    '/de/(.+)/(.+)', 'DetailError',
    '/de/(.+)', 'DetailError',
    '/de', 'DetailError',
)

manage = web.application(urls, locals())


class ologin:

    def GET(self):
        try:
            if ctx.session.uid == ADMIN_WEIBO_ID:
                raise web.seeother('/manage/panel')
        except AttributeError:
            pass
        return render.ologin(auth_url=AUTH_URL)


class callback:

    def GET(self):

        try:
            code = web.ctx.query.split('=')[1]
        except IndexError:
            raise web.seeother(AUTH_URL)
        if len(code)!=32:
            raise web.seeother(AUTH_URL)

        _r = CLIENT.request_access_token(code)
        access_token = _r.access_token
        expires_in = _r.expires_in

        CLIENT.set_access_token(access_token, expires_in)

        try:
            uid = CLIENT.account.get_uid.get()['uid']
            if uid != ADMIN_WEIBO_ID:
                return render.ologin(auth_url=AUTH_URL, error='欢迎尝试')
            ctx.session['uid'] = uid
        except APIError:
            raise web.seeother('../manage')


        raise web.seeother('panel')


def pre_request():
    ''' 访问限制
    '''

    if web.ctx.path not in ['', '/callback']:
        try:
            if ctx.session.uid != ADMIN_WEIBO_ID:
                raise web.seeother('../manage')
        except AttributeError:
            raise web.seeother('../manage')


class panel:
    """ 后台面板首页
    """

    def GET(self):

        return render.panel(item=False)

class now:

    def GET(self):


        data = {
                'session': redis2s.get_count('SESSION*'),
                'user': redis2s.get_count('user*'),
                }

        return render.panel(item=False, opera='now', data=data)

class analytics:
    """ 数据统计
    """

    def GET(self):
        try:
            data = web.input(_method='GET')
            li = ('internalerror', 'checkcode')
            if data.zero in li: mongo2s.set_zero(data.zero)
            raise web.seeother('analytics')
        except AttributeError:
            pass
        coll = db.analytics
        times = {
                'internalerror': coll.find_one({'item':'internalerror'})['times'],
                'checkcode': db.checkcodes.count(),
                }
        return render.panel(item=None, opera='analytics',
                            times=times)

class readlog:
    """ 查看网站日志
    """

    def readfile(self, line):
        # log_pwd = "/home/group/gotit/log/gotit2-stderr.log"
        log_pwd = rds.get('log_file_path')
        with open(log_pwd) as fi:
            all_lines = fi.readlines()
            counts = len(all_lines)
            for lno, li in enumerate(all_lines):
                if lno >= counts-int(line)*50:
                    yield li


    def GET(self, line):

        lines = self.readfile(line)
        return render.panel(item=None, opera='readlog', lines=lines)


class backup:
    """ mongodb数据库的备份与恢复
    """

    def GET(self, label=None):

        if label=='download':

            mongoexport_path = rds.get('mongoexport_path')
            # 备份mongodb数据库，打包成zip文件并返回下载
            dt=datetime.datetime.now()
            filename = '/tmp/gotit-backup-{}'.format(dt.strftime('%Y%m%d%H%M%S'))
            os.system('{} -d gotit -o {}'.format(mongoexport_path, filename))
            ret = zipf2strio(filename) # 打包写入StringIO对象
            try:
                import shutil
                shutil.rmtree(filename) # 删除备份文件夹
            except OSError:
                pass
            web.header('Content-Type','application/octet-stream')
            web.header('Content-disposition', 'attachment; filename=%s.zip' % filename[5:])
            return ret.getvalue()

        return render.panel(item=None, opera='backup')

    #def POST(self, label=None):

    #    x = web.input(myfile={})
    #    ret=web.debug(x['myfile'])
    #    return ret


class update:

    item_list = ['donate', 'zheng', 'cet', 'notice', 'score', 'wxcomment', 'jumbotron']
    opera_list = ['cr', 'del', 'ls', 'info']

    def GET(self, opera, item, oid=None):

        if item in self.item_list and opera in self.opera_list:

            if opera == 'ls':
                ls = db[item].find().sort("datetime",-1)
                return render.panel(item=item, opera=opera, ls=ls)

        return render.panel(item=item, opera=opera, oid=oid)

    def POST(self, opera, item, oid=None):

        data = web.input()

        if item in self.item_list and opera in self.opera_list:

            if opera == 'cr' :
                if item == 'donate':
                    db.donate.insert({
                        'name':data['name'],
                        'much':float(data['much']),
                        'datetime': datetime.datetime.now(),
                        })
                else:
                    db[item].insert({
                        'content':data['content'],
                        'datetime': datetime.datetime.now(),
                        })
            elif opera == 'del':
                db[item].remove({'_id':ObjectId(data['oid'])})

        raise web.seeother('/o/ls/'+item)


class DetailError:
    """查看redis中保存的hash错误
    """

    def GET(self, key=None, hkey=None, do=None):

        content = None
        key_list = None

        if do == "del":
            rds.hdel(key, hkey)
            raise web.seeother("/de/{}".format(key))

        if hkey:
            content = rds.hget(key, hkey)
        elif key:
            key_list = rds.hkeys(key)
        else:
            key_list = rds.keys("error_*")

        return render.panel(item=False, opera='detail_error',
            key=key, hkey=hkey, key_list=key_list, content=content)


manage.add_processor(web.loadhook(pre_request))
