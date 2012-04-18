# coding=utf-8

import urllib,re,sys

from google.appengine.ext import webapp,db
from google.appengine.ext.webapp.util import run_wsgi_app

sys.path.insert(0, 'weibopy.zip')
sys.path.append('weibopy.zip/weibopy')
sys.path.insert(0, 'tweepy.zip')
sys.path.append('tweepy.zip/tweepy')

import tweepy
from weibopy.auth import OAuthHandler
from weibopy.api import API
from weibopy.error import WeibopError

# twitter and sina app key
app_key = '3275848911'
app_secret = 'a9e5b80ec14bcdafd19ac2d47173aa92'
consumer_key = "D7JSMFuPyFRUIKLz0vKTw"
consumer_secret = "OthracjKzuvRYbnWUyJRYeMnLELf7xxmSNmCv78qPnk"

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
<head><title>Tui2Lang-Home</title></head>
<body><center>
<h1>Tui2Lang</h1>
<h3>A new self-service Twitter2Sina Sync application</h3>
<form action="/result" method="post">
<table>
<tr><td>Twitter name: </td><td><input type="text" name="t_name" /></td><td></td></tr>
<tr><td>Twitter Oauth PIN: </td><td><input type="text" name="t_pin" /></td><td><a href="%s" target="_blank">Get Twitter Oauth Pin</a></td></tr>
<tr><td>Sina email: </td><td><input type="text" name="s_name" /></td><td></td></tr>
<tr><td>Sina Oauth PIN: </td><td><input type="text" name="s_pin" /></td><td><a href="%s" target="_blank">Get Sina Oauth Pin</a></td></tr>
</table>
<input type="hidden" name="t_request_key" value="%s"><br>
<input type="hidden" name="t_request_secret" value="%s"><br>
<input type="hidden" name="s_request_key" value="%s"><br>
<input type="hidden" name="s_request_secret" value="%s"><br>
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
    sina_access_key = db.StringProperty()
    sina_access_secret = db.StringProperty()
    twitter_access_key = db.StringProperty()
    twitter_access_secret = db.StringProperty()
    twitter_last_id = db.StringProperty()

class MainPage(webapp.RequestHandler):
    def get(self):
        sina = OAuthHandler(app_key,app_secret)
        sina_auth_url = sina.get_authorization_url()
        twitter = tweepy.OAuthHandler(consumer_key,consumer_secret)
        twitter_auth_url = twitter.get_authorization_url()
        self.response.out.write(html_src % (twitter_auth_url,sina_auth_url,twitter.request_token.key,twitter.request_token.secret,sina.request_token.key,sina.request_token.secret))

class FormHandler(webapp.RequestHandler):
    def post(self):
        t_name = self.request.get('t_name')
        s_name = self.request.get('s_name')
        s_request_key = self.request.get('s_request_key')
        s_request_secret = self.request.get('s_request_secret')
        t_request_key = self.request.get('t_request_key')
        t_request_secret = self.request.get('t_request_secret')
        t_pin = self.request.get('t_pin')
        s_pin = self.request.get('s_pin')
        self.response.out.write("""<html><head><title>Tui2Lang-Result</title></head><body><center>""")
        if t_name == "" or s_name =="" or s_pin == "":
            self.response.out.write("""<h2>4 Input can not be empty! <a href="/">Back</a></h2>""")
        else:
            sina = OAuthHandler(app_key,app_secret)
            sina.set_request_token(s_request_key,s_request_secret)
            s_access_token = sina.get_access_token(s_pin.strip())
            sina_api = API(sina)

            twitter = tweepy.OAuthHandler(consumer_key,consumer_secret)
            twitter.set_request_token(t_request_key,t_request_secret)
            t_access_token = twitter.get_access_token(t_pin.strip())
            twitter_api = tweepy.API(twitter);
            
            t_tl = twitter_api.user_timeline()
            t_last_id = t_tl[0].id_str
            t_last_text = replace_tweet(t_tl[0].text)
            

            oauth_user = OauthUser(key_name=s_name)
            oauth_user.twitter_name = t_name
            oauth_user.sina_name = s_name
            oauth_user.sina_access_key = s_access_token.key
            oauth_user.sina_access_secret = s_access_token.secret
            oauth_user.twitter_access_key = t_access_token.key
            oauth_user.twitter_access_secret = t_access_token.secret
            oauth_user.twitter_last_id = t_last_id
            oauth_user.put()

            try:
                sina_api.update_status(t_last_text)            
            except WeibopError,e:
                self.response.out.write(e)
            else:
                self.response.out.write('Your Tui2Lang settings are successfully done!<br>')
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
			if tl.source.find(unicode('街旁(JiePang)','utf8')) == -1  or tl.source.find('Instagram') == -1:
			    tweets_to_be_post.append({'id_str':tl.id_str,'text':tl.text})
                    else:
                        break
                if len(tweets_to_be_post) > 0:
                    # rebuild sina api
                    sina = OAuthHandler(app_key,app_secret)
                    sina.set_access_token(result.sina_access_key,result.sina_access_secret)
                    sina_api = API(sina)
                    
                    for tweet_obj in reversed(tweets_to_be_post):
                        user = OauthUser.get_by_key_name(result.sina_name)
                        cur_id = tweet_obj['id_str']
                        cur_tweet = tweet_obj['text']
                        if cur_tweet.find('#nosina') != -1 or cur_tweet.startswith('@'):
                            continue
                        tweet = replace_tweet(cur_tweet)
			self.response.out.write(tweet)
                        try:
                            sina_api.update_status(tweet)
                            user.twitter_last_id = cur_id
                            user.put()
                            self.response.out.write('同步成功！')
                        except WeibopError,e:
                            self.response.out.write(e)
                            self.response.out.write('<br>')


application = webapp.WSGIApplication(
    [('/', MainPage),
     ('/result', FormHandler),
     ('/cron_sync', AutoSync),
     ],
    debug = True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()       