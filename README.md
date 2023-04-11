# acfun直播爱咔录播链接查询记录工具
acfun直播爱咔录播链接查询记录工具，可用于记录你需要关注的主播的爱咔录播链接，本脚本运行后会定期查询acfun直播列表，并记录下对应的爱咔录播URL。
## 安装依赖
```
pip3 install -r requirements.txt
```
## 运行
### 运行记录脚本
```
python3 acfun_live.py 
```
首次运行时会自动创建配置文件`config.json`，可向`targe_uid`参数添加要监听的主播的uid，参数`interval`为查询间隔时间（分钟）
```
{
    "targe_uid": [], 
    "interval": 1
}
```

脚本运行后会定时查询记录，记录保存在`liveika.db`文件中，可通过sqlite工具查看。

### 查询本地记录
查询本地记录并输出到文件，默认输出文件名为`out.txt`
```
python3 acfun_live.py -l [-f] [outputfilename]
```
可通过-f 指定输出记录文件名