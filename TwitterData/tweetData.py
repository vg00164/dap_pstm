import re 
import tweepy 
from tweepy import OAuthHandler 
from textblob import TextBlob
import mysql.connector as mc
import configparser
import io
import datetime
import pandas as pd

class TwitterClient(object): 
	''' 
	Generic Twitter Class for sentiment analysis. 
	'''
	def __init__(self): 
		''' 
		Class constructor or initialization method. 
		'''

		config = configparser.ConfigParser()
		config.read('config.ini')
		# keys and tokens from the Twitter Dev Console 
		consumer_key = config['TWITTER']['consumer_key']
		consumer_secret = config['TWITTER']['consumer_secret']
		access_token = config['TWITTER']['access_token']
		access_token_secret = config['TWITTER']['access_token_secret']

		# attempt authentication 
		try: 
			# create OAuthHandler object 
			self.auth = OAuthHandler(consumer_key, consumer_secret) 
			# set access token and secret 
			#self.auth.set_access_token(access_token, access_token_secret) 
			# create tweepy API object to fetch tweets 
			self.api = tweepy.API(self.auth) 
		except: 
			print("Error: Authentication Failed") 

	def clean_tweet(self, tweet): 
		''' 
		Utility function to clean tweet text by removing links, special characters 
		using simple regex statements. 
		'''
		return ' '.join(re.sub("(@[A-Za-z0-9]+)|([^0-9A-Za-z \t]) |(\w+:\/\/\S+)", " ", tweet).split()) 

	def get_tweet_sentiment(self, tweet): 
		''' 
		Utility function to classify sentiment of passed tweet 
		using textblob's sentiment method 
		'''
		# create TextBlob object of passed tweet text 
		analysis = TextBlob(self.clean_tweet(tweet)) 
		# set sentiment 
		if analysis.sentiment.polarity > 0: 
			return 'positive'
		elif analysis.sentiment.polarity == 0: 
			return 'neutral'
		else: 
			return 'negative'

	def get_tweets(self, topic_Entity_id, query, count = 10): 
		''' 
		Main function to fetch tweets and parse them. 
		'''
		print("******Searching for the Keyword**** : ",query)
		# empty list to store parsed tweets 
		tweets = [] 

		try: 
			# call twitter api to fetch tweets 
			#fetched_tweets = self.api.search(q = query, count = count) 
			sinceDate = datetime.date.today() - datetime.timedelta(1)
			untilDate = datetime.date.today()
			fetched_tweets = tweepy.Cursor(self.api.search, q=query, since=sinceDate,until=untilDate, lang='en')
			# parsing tweets one by one 
			for tweet in fetched_tweets.items(count): 
				# empty dictionary to store required params of a tweet 
				parsed_tweet = {} 

				parsed_tweet['Tweet_Id'] = tweet.id_str
				parsed_tweet['Tweet_date'] = tweet.created_at
				# saving text of tweet 
				parsed_tweet['Text'] = tweet.text 
				
				#parsed_tweet['Text'] = ''
				hashtag = ''
				for hashtags in tweet.entities['hashtags']:
					if hashtags != '':
						hashtag = hashtag + '~' + hashtags['text']
				parsed_tweet['Hashtag'] = hashtag

				expanded_url = ''
				for urls in tweet.entities['urls']:
					expanded_url = urls['expanded_url']
				parsed_tweet['Expanded_Url'] = expanded_url
				parsed_tweet['iso_language_code'] = tweet.metadata['iso_language_code']
				parsed_tweet['in_reply_to_status_id'] = tweet.in_reply_to_status_id_str
				parsed_tweet['in_reply_to_user_id'] = tweet.in_reply_to_user_id_str
				parsed_tweet['in_reply_to_screen_name'] = tweet.in_reply_to_screen_name

				# user Data
				parsed_tweet['User_Id'] = tweet.user.id_str
				parsed_tweet['User_Name'] = tweet.user.name
				parsed_tweet['User_Screen_Name'] = tweet.user.screen_name
				parsed_tweet['User_Location'] = tweet.user.location
				
				#retweet data
				if hasattr(tweet, 'retweeted_status'):
					parsed_tweet['Original_Tweet_Id']	= tweet.retweeted_status.id_str
					parsed_tweet['Original_Tweet_Date'] = tweet.retweeted_status.created_at
					parsed_tweet['Original_Text'] = tweet.retweeted_status.text
					parsed_tweet['Original_User_Id'] = tweet.retweeted_status.user.id_str
					parsed_tweet['Original_User_Name'] = tweet.retweeted_status.user.name
					parsed_tweet['Original_User_Screen_Name'] = tweet.retweeted_status.user.screen_name
					parsed_tweet['Original_User_Location'] = tweet.retweeted_status.user.location
				else:
					parsed_tweet['Original_Tweet_Id'] = ''
					parsed_tweet['Original_Tweet_Date'] = ''
					parsed_tweet['Original_Text'] = ''
					parsed_tweet['Original_User_Id'] = ''
					parsed_tweet['Original_User_Name'] = ''
					parsed_tweet['Original_User_Screen_Name'] = ''
					parsed_tweet['Original_User_Location'] = ''
				#Topic Data

				parsed_tweet['Topic_Entity_Id'] = topic_Entity_id
				parsed_tweet['Created_Date'] = datetime.date.today()
				parsed_tweet['Modified_Date'] = datetime.date.today()
				# saving sentiment of tweet 
				parsed_tweet['Sentiment_Type'] = self.get_tweet_sentiment(tweet.text).upper()
				parsed_tweet['Sentiment_Percentage'] = 1
				# appending parsed tweet to tweets list 
				if tweet.retweet_count > 0: 
					# if tweet has retweets, ensure that it is appended only once 
					if parsed_tweet not in tweets: 
						tweets.append(parsed_tweet) 
				else: 
					tweets.append(parsed_tweet) 

			# return parsed tweets 
			return tweets 

		except tweepy.TweepError as e: 
			# print error (if any) 
			print("Error : " + str(e))


#get the database connection. database name is dapanalysis 
def get_connection():
	config = configparser.ConfigParser()
	config.read('config.ini')
	user = config['MYSQL']['user']
	passwd = config['MYSQL']['passwd']
	host = config['MYSQL']['host']
	database = config['MYSQL']['database']
	auth = config['MYSQL']['auth_plugin']
	return mc.connect(user=user,password=passwd,host=host, database=database,auth_plugin=auth)

# Read the topics from DB
def read_topics():
	topic_select = 'select a.topic_id,a.Name, b.Topic_Entity_Id,b.Entity_Type,b.Entity_Value from topics_tbl a, topic_entities_tbl b where a.topic_id = b.topic_id and a.Active_flag = 1 and b.Active_flag=1'
	result_set = run_query(topic_select)
	return result_set
	#for n in result_set:
		#print('id : ',n[0], "description :", n[1])
    
def run_query(sql):
    connection = get_connection()
    connection.cmd_query(sql)
    result_set_and_meta = connection.get_rows()
    result_set = result_set_and_meta[0]
    connection.close()
    return result_set

def saveDatatoDB(df,table):
	print("------Saving Data into table-----",table)
	try:
		connection = get_connection()
		value_string = ', '.join(['%s' for _ in range(len(df.columns))])
		columns = ', '.join([col_name for col_name in df.columns])
		cursor = connection.cursor()
		cursor.executemany(
                               """INSERT IGNORE INTO {} ({}) VALUES ({})""".format(table, columns, value_string),
                               df.values.tolist())
		connection.commit()
		cursor.close()
		connection.close()
		print("------Successfully saved data into the table-----",table)
	except Exception as e:
		print(e)
		cursor.close()
		connection.close()


def main(): 
	# creating object of TwitterClient Class 
	api = TwitterClient() 

	#Read topics from database

	results = read_topics()

	for topic in results:
		Topic_Entity_Id = topic[2]
		Topic_Entity_Value = topic[4]
		# calling function to get tweets 
		tweets = api.get_tweets(topic_Entity_id=Topic_Entity_Id,query = Topic_Entity_Value, count = 200)

		tweetsDF = pd.DataFrame(tweets)
		tweetsDFCopy = tweetsDF.copy
		twitterDataDF = tweetsDF.drop(['Sentiment_Type','Sentiment_Percentage'],axis=1)
		
		saveDatatoDB(twitterDataDF,'twitter_data_tbl')
		sentimentDataDF = tweetsDF[['Tweet_Id','Topic_Entity_Id','Sentiment_Type','Sentiment_Percentage','Created_Date','Modified_Date']]
		saveDatatoDB(sentimentDataDF,'twitter_sentiments_tbl')
		
		# picking positive tweets from tweets 
		ptweets = [tweet for tweet in tweets if tweet['Sentiment_Type'] == 'positive'] 
		# percentage of positive tweets 
		print("Positive tweets percentage: {} %".format(100*len(ptweets)/len(tweets))) 
		# picking negative tweets from tweets 
		ntweets = [tweet for tweet in tweets if tweet['Sentiment_Type'] == 'negative'] 
		# percentage of negative tweets 
		print("Negative tweets percentage: {} %".format(100*len(ntweets)/len(tweets))) 
		# percentage of neutral tweets 
		#print("Neutral tweets percentage: {} %".format(100*len(tweets - ntweets - ptweets)/len(tweets))) 

		# printing first 5 positive tweets 
		print("\n\nPositive tweets:") 
		for tweet in ptweets[:10]: 
			print(tweet['Text']) 

		# printing first 5 negative tweets 
		print("\n\nNegative tweets:") 
		for tweet in ntweets[:10]: 
			print(tweet['Text']) 

	

if __name__ == "__main__": 
	# calling main function 
	main() 

