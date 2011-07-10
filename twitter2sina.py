# coding=utf-8

import urllib,re,sys
import simplejson as json
from google.appengine.ext import webapp,db
from google.appengine.ext.webapp.util import run_wsgi_app

sys.path.insert(0, 'weibopy.zip')
sys.path.append('weibopy.zip/weibopy')

from weibopy.auth import OAuthHandler
from weibopy.api import API
from weibopy.error import WeibopError


app_key = '3275848911'
app_secret = 'a9e5b80ec14bcdafd19ac2d47173aa92'
t_timeline_url = 'http://twitter.com/statuses/user_timeline/%s.json'
re_username = re.compile(r'@([a-z|A-Z|0-9|_]+):?')
re_name_prefix = re.compile(r'@\[')
re_tag = re.compile(r'#(\w+)')
re_rt1 = re.compile(r'(RT)@')
re_rt2 = re.compile(r'(RT\s+)@')

html_src = """
<html>
<head><title>Tui2Lang-Home</title></head>
<body><center>
<h1>Tui2Lang</h1>
<h3>A new self-service Twitter2Sina Sync application</h3>
<form action="/result" method="post">
<table>
<tr><td>Twitter name: </td><td><input type="text" name="t_name" /></td><td></td></tr>
<tr><td>Sina name: </td><td><input type="text" name="s_name" /></td><td></td></tr>
<tr><td>Oauth PIN: </td><td><input type="text" name="s_pin" /></td><td><a href="%s" target="_blank">Get Sina Oauth Pin</a></td></tr>
</table>
<input type="hidden" name="s_request_key" value="%s"><br>
<input type="hidden" name="s_request_secret" value="%s"><br>
<input type="submit" value="Submit">
</center></body>
</html>
"""


def replace_tweet(tweet):
    for ind,re_str in enumerate([re_username, re_tag]):
        matches = set(re_str.findall(tweet))
        if matches != ['']:
            for m in matches:
                if ind == 0:
                    tweet = tweet.replace(m, '[%s]' % m)
                elif ind == 1:
                    tweet = tweet.replace(m, '%s#' % m)
    
    for re_str in [re_rt1, re_rt2]:
        matches = set(re_str.findall(tweet))
        if matches != ['']:
            tweet = re_str.sub(unicode('转发自','utf8'),tweet)
    tweet = re_name_prefix.sub('[',tweet)
    return tweet
         


class OauthUser(db.Model):
    twitter_name = db.StringProperty()
    sina_name = db.StringProperty()
    sina_access_key = db.StringProperty()
    sina_access_secret = db.StringProperty()
    twitter_last_id = db.StringProperty()

class MainPage(webapp.RequestHandler):
    def get(self):
        auth = OAuthHandler(app_key,app_secret)
        auth_url = auth.get_authorization_url()
        self.response.out.write(html_src % (auth_url,auth.request_token.key,auth.request_token.secret))
        
class FormHandler(webapp.RequestHandler):
    def post(self):
        t_name = self.request.get('t_name')
        s_name = self.request.get('s_name')
        s_pin = self.request.get('s_pin')
        self.response.out.write("""<html><head><title>Tui2Lang-Result</title></head><body><center>""")
        if t_name == "" or s_name =="" or s_pin == "":
            self.response.out.write("""<h2>3 Input can not be empty! <a href="/">Back</a></h2>""")
        else:
            s_request_key = self.request.get('s_request_key')
            s_request_secret = self.request.get('s_request_secret')
            auth = OAuthHandler(app_key,app_secret)
            auth.set_request_token(s_request_key,s_request_secret)
            s_access_token = auth.get_access_token(s_pin.strip())
            api = API(auth)
            
            t_tl_file = urllib.urlopen(t_timeline_url % t_name)
            t_tl = json.load(t_tl_file)
            t_last_id = t_tl[0].get('id_str')
            t_last_text = replace_tweet(t_tl[0].get('text'))
            
            oauth_user = OauthUser(key_name=s_name)
            oauth_user.twitter_name = t_name
            oauth_user.sina_name = s_name
            oauth_user.sina_access_key = s_access_token.key
            oauth_user.sina_access_secret = s_access_token.secret
            oauth_user.twitter_last_id = t_last_id
            oauth_user.put()
            
            try:
                api.update_status(t_last_text)                
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
                tl_file = urllib.urlopen(t_timeline_url % result.twitter_name)
                timeline = json.load(tl_file)
                if isinstance(timeline,list):
                    last_id = int(result.twitter_last_id)
                    tweets_to_be_post = []
                    for tl in timeline:
                        if int(tl['id_str']) > last_id:
                            tweets_to_be_post.append({'id_str':tl['id_str'],'text':tl['text']})
			else:
				break
		if len(tweets_to_be_post) > 0:
			auth = OAuthHandler(app_key,app_secret)
			auth.set_access_token(result.sina_access_key,result.sina_access_secret)
			api = API(auth)
			for tweet_obj in reversed(tweets_to_be_post):
				user = OauthUser.get_by_key_name(result.sina_name)
				cur_id = tweet_obj['id_str']
				cur_tweet = tweet_obj['text']
				if cur_tweet.find('#nosina') != -1 or cur_tweet.startswith('@'):
					continue
				tweet = replace_tweet(cur_tweet)
				try:
					api.update_status(tweet)
					user.twitter_last_id = cur_id
					user.put()
				except WeibopError,e:
					self.response.out.write(e)
					self.response.out.write('<br>')
                else:
                    self.response.out.write('Get Timeline Error!')
                
        
        
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