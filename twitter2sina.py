# coding=utf-8

import urllib,re,sys

from google.appengine.ext import webapp,db
from google.appengine.ext.webapp.util import run_wsgi_app

sys.path.insert(0, 'tweepy.zip')
sys.path.append('tweepy.zip/tweepy')

import tweepy
from weibo import APIClient, APIError

# twitter and sina app key
APP_KEY = ""  # your sina app key
APP_SECRET = "" # your sina app secret
S_CALLBACK = "" # http://your_gae_url/oauth
CONSUMER_KEY = "D7JSMFuPyFRUIKLz0vKTw"
CONSUMER_SECRET = "OthracjKzuvRYbnWUyJRYeMnLELf7xxmSNmCv78qPnk"

# regular expressions
re_username = re.compile(r'@([a-z|A-Z|0-9|_]+):?')
re_name_prefix = re.compile(r'@\[')
re_tag = re.compile(r'#(\w+)')
re_rt1 = re.compile(r'(RT)@')
re_rt2 = re.compile(r'(RT\s+)@')
re_url = re.compile('http.?://[^\ ]+')
re_url_head = re.compile('http.?://')
re_fetch_url = re.compile('<a href="(.*)">')

html_src = """
<html>
<head><title>Twitter2Sina-Home</title></head>
<body><center>
<h1>Twitter2Sina</h1>
<h3>A new self-service Twitter2Sina Sync application</h3>
<form action="/result" method="post">
<table>
<tr><td>Twitter name: </td><td><input type="text" name="t_name" /></td></tr>
<tr><td>Twitter Oauth PIN: </td><td><input type="text" name="t_pin" /></td><td><a href="%s" target="_blank">Get Twitter Oauth Pin</a></td></tr>
<tr><td>Sina name: </td><td><input type="text" name="s_name" value="%s" /></td></tr>
</table>
<input type="hidden" name="t_request_key" value="%s"><br>
<input type="hidden" name="t_request_secret" value="%s"><br>
<input type="hidden" name="s_access_token" value="%s"><br>
<input type="hidden" name="s_expire" value="%s"><br>
<input type="submit" value="Submit">
</center></body>
</html>
"""


def replace_tweet(tweet):
    # replace @username to [username]
    # replace #tag to #tag#
    for ind,re_str in enumerate([re_username, re_tag]):
        matches = set(re_str.findall(tweet))
        if matches != ['']:
            for m in matches:
                if ind == 0:
                    tweet = tweet.replace(m, '[%s]' % m)
                elif ind == 1:
                    tweet = tweet.replace(m, '%s#' % m)
	
    # replace RT to 转发自
    for re_str in [re_rt1, re_rt2]:
        matches = set(re_str.findall(tweet))
        if matches != ['']:
            tweet = re_str.sub(unicode('转发自','utf8'),tweet)
    tweet = re_name_prefix.sub('[',tweet)
	
    # expand t.co
    matches = re_url.findall(tweet)
    if matches != ['']:
	for m in matches:
	    url = re_url_head.sub('',m)
	    html = urllib.urlopen('http://233.im/%s' % url).read()
	    real_url = re_fetch_url.findall(html)[0]
	    if real_url[-1] == '\r':
		real_url = real_url[:-1]
	    tweet = re_url.sub(real_url,tweet)
    return tweet

class OauthUser(db.Model):
    twitter_name = db.StringProperty()
    sina_name = db.StringProperty()
    sina_access_token = db.StringProperty()
    sina_expire = db.StringProperty()
    twitter_access_key = db.StringProperty()
    twitter_access_secret = db.StringProperty()
    twitter_last_id = db.StringProperty()

class MainPage(webapp.RequestHandler):
    def get(self):
        sina = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=S_CALLBACK)
        sina_auth_url = sina.get_authorize_url()
        self.response.out.write("""<a href="%s">Sina Oauth</a>""" % sina_auth_url)
        
        
class Oauth(webapp.RequestHandler):
    def get(self):
        s_pin = self.request.get('code')
        if s_pin:
            sina = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=S_CALLBACK)
            r = sina.request_access_token(s_pin)
            sina.set_access_token(r.access_token,r.expires_in)
            twitter = tweepy.OAuthHandler(CONSUMER_KEY,CONSUMER_SECRET)
            twitter_auth_url = twitter.get_authorization_url()
            self.response.out.write(html_src % (twitter_auth_url,sina.users__show(uid=r.uid).screen_name,twitter.request_token.key,twitter.request_token.secret,r.access_token,r.expires_in))
        else:
            self.response.out.write("""<p>Error!!!<a href="/">Home</a></p>""")
        

class FormHandler(webapp.RequestHandler):
    def post(self):
        t_name = self.request.get('t_name')
        s_name = self.request.get('s_name')
        s_access_token = self.request.get('s_access_token')
        s_expire = self.request.get('s_expire')
        t_request_key = self.request.get('t_request_key')
        t_request_secret = self.request.get('t_request_secret')
        t_pin = self.request.get('t_pin')
        self.response.out.write("""<html><head><title>Twitter2Sina-Result</title></head><body><center>""")
        if t_name == "" or s_name =="":
            self.response.out.write("""<h2>4 Input can not be empty! <a href="/">Back</a></h2>""")
        else:
            sina_api = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=S_CALLBACK)
            sina_api.set_access_token(s_access_token,int(s_expire))
            
            twitter = tweepy.OAuthHandler(CONSUMER_KEY,CONSUMER_SECRET)
            twitter.set_request_token(t_request_key,t_request_secret)
            t_access_token = twitter.get_access_token(t_pin.strip())
            twitter_api = tweepy.API(twitter);
            
            t_tl = twitter_api.user_timeline()
            t_last_id = t_tl[0].id_str
            t_last_text = replace_tweet(t_tl[0].text)

            oauth_user = OauthUser(key_name=t_name)
            oauth_user.twitter_name = t_name
            oauth_user.sina_name = s_name
            oauth_user.sina_access_token = s_access_token
            oauth_user.sina_expire = s_expire
            oauth_user.twitter_access_key = t_access_token.key
            oauth_user.twitter_access_secret = t_access_token.secret
            oauth_user.twitter_last_id = t_last_id
            oauth_user.put()

            try:
                sina_api.post.statuses__update(status=t_last_text)            
            except APIError,e:
                self.response.out.write(e)
            else:
                self.response.out.write('Your Twitter2Sina settings are successfully done!<br>')
                self.response.out.write('The last tweet synchronized is below:<br>')
                self.response.out.write('<b>%s</b>' % t_last_text)
        self.response.out.write('</center></body></html>')


class AutoSync(webapp.RequestHandler):
    def get(self):
        query = db.GqlQuery("SELECT * FROM OauthUser")
        if query.count() > 0:
            for result in query:
                # rebuild twitter api
                twitter = tweepy.OAuthHandler(consumer_key,consumer_secret)
                twitter.set_access_token(result.twitter_access_key,result.twitter_access_secret)
                twitter_api = tweepy.API(twitter)
                
                timeline = twitter_api.user_timeline()
                last_id = result.twitter_last_id
                tweets_to_be_post = []
                for tl in timeline:
		    # disable jiepang
                    if int(tl.id_str) > int(last_id):
			if tl.source.find(unicode('街旁(JiePang)','utf8')) == -1  and tl.source.find('Instagram') == -1:
			    tweets_to_be_post.append({'id_str':tl.id_str,'text':tl.text})
                    else:
                        break
                if len(tweets_to_be_post) > 0:
                    # rebuild sina api
                    sina_api = APIClient(app_key=APP_KEY, app_secret=APP_SECRET, redirect_uri=S_CALLBACK)
                    sina_api.set_access_token(result.s_access_token,int(result.s_expire))
                    
                    for tweet_obj in reversed(tweets_to_be_post):
                        user = OauthUser.get_by_key_name(result.sina_name)
                        cur_id = tweet_obj['id_str']
                        cur_tweet = tweet_obj['text']
                        if cur_tweet.find('#nosina') != -1 or cur_tweet.startswith('@'):
                            continue
                        tweet = replace_tweet(cur_tweet)
			self.response.out.write(tweet)
                        try:
                            sina_api.post.statuses__update(status=tweet)
                            user.twitter_last_id = cur_id
                            user.put()
                            self.response.out.write('同步成功！')
                        except APIError,e:
                            self.response.out.write(e)
                            self.response.out.write('<br>')


application = webapp.WSGIApplication(
    [('/', MainPage),
    ('/oauth', Oauth),
     ('/result', FormHandler),
     ('/cron_sync', AutoSync),
     ],
    debug = True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()       
