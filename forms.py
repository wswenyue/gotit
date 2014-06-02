#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from web import form

# forms
cet_form = form.Form(
    form.Textbox(
        "zkzh",
        description="准考证号:",
        class_="span3",
        pre="&nbsp;&nbsp;"),
    form.Textbox(
        "name",
        description="姓名:",
        class_="span3",
        pre="&nbsp;&nbsp;"),
    validators=[
        form.Validator('输入不合理!', lambda i:int(i.zkzh) != 15)]
)

xh_form = form.Form(
    form.Textbox("xh", form.notnull, description="* 学号"),
    validators = [
        form.Validator("格式错误", lambda i: re.match(re.compile("\d+"), i.xh))
    ]
)

login_form = form.Form(
    form.Textbox(
        "xh",
        description="学号:",
        class_="span3",
        pre="&nbsp;&nbsp;"),
    form.Password(
        "pw",
        description="密码:",
        class_="span3",
        pre="&nbsp;&nbsp;"),
    validators=[
        form.Validator('输入不合理!', lambda i: len(i.xh)<=12 and len(i.xh)>=9)
    ]
)

cron_form = form.Form(
    form.Textbox('name', form.notnull, description="*真实姓名"),
    form.Textbox('xh', form.notnull, description="*学号"),
    form.Password('pw', form.notnull, description="*密码(正方教务系统密码)"),
    # form.Password('lib_pw', description="密码(图书馆密码)"),
    form.Textbox('email', form.notnull, description="*电子邮箱"),
    form.Textbox('alipay', form.notnull, description="*支付宝账户"),
    validators=[
        form.Validator('学号格式错误!', lambda i: len(i.xh)<=12 and len(i.xh)>=9)
    ]
)