import base64
from time import gmtime, strftime
import time
from boto3.dynamodb.conditions import Key, Attr
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
import json
import sys, linecache
import re
import collections
import os
from multiprocessing.pool import ThreadPool
from pprint import pprint
import uuid

sourceLanguage = 'en'
translateLanguages = 'en, es, fr, de'

# DYNAMO Global Vars
DYNAMO_CONFIG = Config(connect_timeout=0.250, read_timeout=0.250, retries={'max_attempts': 2})
DYNAMO_RESOURCE = boto3.resource('dynamodb', config=DYNAMO_CONFIG)

POOL = ThreadPool(processes=16)

DEBUG = False

# Put the translated languages 
def put_all_transcriptions(all_t, payload, dynamo_table):
    for key, value in all_t.items(): 
        this_payload = payload.copy()
        this_payload['id_name'] = str(uuid.uuid4())
        this_payload['id_lang'] = key
        this_payload['transcript_transcript'] = value
        put_dynamo(this_payload, dynamo_table)

# Send the translated languages
def make_all_transcriptions(text, languages, source_lang):
    
    transcripts = {}
    # Start all the threads
    for lang in languages:
        if lang != source_lang:
            transcripts[lang] = POOL.apply_async(get_transcript, (source_lang, lang, text)) 
    # Get the results
    for lang in languages:
        if lang != source_lang:
            transcripts[lang] = transcripts[lang].get()
    return transcripts
  


def get_transcript(source_lang, target_lang, text):
    try:
        # Setup translate client
        config = Config(connect_timeout=1, read_timeout=1, retries={'max_attempts': 2})
        translate = boto3.client('translate', config=config)
        translation = translate.translate_text(Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)['TranslatedText']
        if DEBUG:
            print("DEBUG translation {} from {}: {}".format(target_lang,source_lang,translation))
    except:
        print("WARNING There is no text. Nothing is being said return an empty string")
        return " " #There is no text. Nothing is being said return an empty string. 
    return translation

def put_dynamo(dynamo_object, dynamo_table):
    table = DYNAMO_RESOURCE.Table(dynamo_table)

    try:
        response = table.put_item(
            Item=dynamo_object,
            ConditionExpression='attribute_not_exists(id_name)'
        )
        if DEBUG:
            print("DEBUG dynamo put_item succeeded: {}".format(response))
    except ClientError as e:
        # Ignore the ConditionalCheckFailedException, bubble up other exceptions.
        if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
            print("ERROR ClientError: {}".format(e))
    return response

def str_to_bool(s):
    if s == 'True':
         return True
    elif s == 'true':
         return True
    else:
         return False

def check_debug():
    if os.environ.get('CF5K-DEBUG') is not None:
        global DEBUG
        DEBUG = str_to_bool(os.environ['CF5K-DEBUG'])
        print('DEBUG environment variable DEBUG was found: {}'.format(DEBUG))

def lambda_handler(event, context):
    # Looking for evironment variable overrides
    check_debug()
    source_lang = os.environ.get('SOURCE_LANGUAGE', default=sourceLanguage)
    caption_languages = os.environ.get('CAPTION_LANGUAGES', default=translateLanguages)
    # Make sure that the languages the customer entered are supported. And remove duplicate langauges from input.
    languages = [x.strip() for x in str(caption_languages).split(',')]
    languages = [lang for lang in languages]
    languages = list(collections.OrderedDict.fromkeys(languages))
    dynamo_table = os.environ.get('DYNAMO_TABLE', default=False)
    if not dynamo_table:
        print("ERROR DYNAMO_TABLE not set")
        return False

    payload = json.loads(event['Records'][0]['Sns']['Message'])
    if DEBUG:
        print("DEBUG SNS payload: {}".format(payload))
    text = payload['transcript_transcript']
    all_t = make_all_transcriptions(text, languages, source_lang)
    put_all_transcriptions(all_t, payload, dynamo_table)

    return True