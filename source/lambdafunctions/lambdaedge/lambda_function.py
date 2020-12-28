import base64
from time import gmtime, strftime
import time
from boto3.dynamodb.conditions import Key, Attr
import boto3
from botocore.exceptions import ClientError
import json
import sys, linecache
import re
from botocore.client import Config
from aws_embedded_metrics import metric_scope

# DYNAMO Global Vars
DYNAMO_CONFIG = Config(connect_timeout=0.250, read_timeout=0.250, retries={'max_attempts': 1})
DYNAMO_RESOURCE = boto3.resource('dynamodb', config=DYNAMO_CONFIG)
DYNAMO_TABLE = 'not-set'
DYNAMO_INDEX = "not-set"

# PIPE ID
PIPE_ID = 'not-set'

# CLOUDWATCH Global Vars
CLOUDWATCH_NAMESPACE = 'autocaptions2'

# CAPTION Global Vars
CAPTION_PASSTHROUGH = False
CAPTION_REPLACE = True
CAPTION_BUFFER = 2

DEBUG = False

def get_environment_variables(request):
    global DEBUG
    global CAPTION_PASSTHROUGH
    global CAPTION_REPLACE
    global CAPTION_BUFFER
    global DYNAMO_INDEX
    global DYNAMO_TABLE
    global CLOUDWATCH_NAMESPACE
    global PIPE_ID

    try:
        ## Optional Variables - Debugging / Metrics
        if 'cf5k-debug' in request:
            DEBUG = str_to_bool(request['cf5k-debug'][0]['value'])
            if DEBUG: 
                print('DEBUG GLOBAL customHeader DEBUG: {}'.format(DEBUG))
        if DEBUG:
            print('DEBUG raw list of customHeader: {}'.format(request))

        ## Optional Variables - Features
        # CAPTION_PASSTHROUGH
        if 'caption_passthrough' in request:
            CAPTION_PASSTHROUGH = str_to_bool(request['caption_passthrough'][0]['value'])
            if DEBUG: 
                print('DEBUG GLOBAL customHeader CAPTION_PASSTHROUGH: {}'.format(CAPTION_PASSTHROUGH))
        # CAPTION_REPLACE
        if 'caption_replace' in request:
            CAPTION_REPLACE = str_to_bool(request['caption_replace'][0]['value'])
            if DEBUG: 
                print('DEBUG GLOBAL customHeader CAPTION_REPLACE: {}'.format(CAPTION_REPLACE))
        # CAPTION_BUFFER
        if 'caption_buffer' in request:
            CAPTION_BUFFER = str_to_bool(request['caption_buffer'][0]['value'])
            if DEBUG: 
                print('DEBUG GLOBAL customHeader CAPTION_BUFFER: {}'.format(CAPTION_BUFFER))
        # CLOUDWATCH_NAMESPACE
        if 'cloudwatch_namespace' in request:
            CLOUDWATCH_NAMESPACE = request['cloudwatch_namespace'][0]['value']
            if DEBUG: 
                print('DEBUG GLOBAL customHeader CLOUDWATCH_NAMESPACE: {}'.format(CLOUDWATCH_NAMESPACE))

        ## Mandatory Variables - DynamoDB configuration
        # DYNAMO_INDEX
        if 'dynamo_index' in request:
            DYNAMO_INDEX = request['dynamo_index'][0]['value']
            if DEBUG: 
                print('DEBUG GLOBAL customHeader DYNAMO_INDEX: {}'.format(DYNAMO_INDEX))
        else:
            print("ERROR GLOBAL customHeader DYNAMO_INDEX NOT FOUND!")
            return False
        # DYNAMO_TABLE
        if 'dynamo_table' in request:
            DYNAMO_TABLE = request['dynamo_table'][0]['value']
            if DEBUG: 
                print('DEBUG GLOBAL customHeader DYNAMO_TABLE: {}'.format(DYNAMO_TABLE))
        else:
            print("ERROR GLOBAL customHeader DYNAMO_TABLE NOT FOUND!")
            return False
        # PIPE
        if 'pipe_id' in request:
            PIPE_ID = request['pipe_id'][0]['value']
            if DEBUG: 
                print('DEBUG GLOBAL customHeader PIPE_ID: {}'.format(PIPE_ID))
        else:
            print("ERROR GLOBAL customHeader PIPE_ID NOT FOUND!")
            return False
    except: 
        print("ERROR get_environment_variables Exception")
        print_exception()
        return False

    return True

def str_to_bool(s):
    if s == 'True':
         return True
    elif s == 'true':
         return True
    else:
         return False


def print_exception():
    """
    Informative exception handler
    """
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print('ERROR EXCEPTION IN ({}, LINE {} "{}"): {} {}'.format(filename, lineno, line.strip(), exc_type, exc_obj))


## CLOUDWATCH Metrics
# Counts
@metric_scope
def put_count_metrics(metric_name, metric_value, pipe_id, lang_id, metrics={}):
    if DEBUG: 
        print("DEBUG put_count_metrics {} {} {} {}".format(metric_name, metric_value, pipe_id, lang_id))
    metrics.set_namespace(CLOUDWATCH_NAMESPACE)
    metrics.set_dimensions({ "PipeId": pipe_id, "LanguageId": lang_id, "Type": "Counts" })
    metrics.put_metric(metric_name, metric_value, "Count")

# ProcessTime
@metric_scope
def put_duration_metrics(metric_name, start, end, pipe_id, lang_id, metrics={}):
    if DEBUG: 
        print("DEBUG put_duration_metrics {} {} {} {} {}".format(metric_name, start, end, pipe_id, lang_id))
    duration = end - start
    metrics.set_namespace(CLOUDWATCH_NAMESPACE)
    metrics.set_dimensions({ "PipeId": pipe_id, "LanguageId": lang_id, "Type": "ProcessTime" })
    metrics.put_metric(metric_name, duration, "Seconds")

# Durations
@metric_scope
def put_known_duration_metrics(metric_name, duration, pipe_id, lang_id, metrics={}):
    if DEBUG: 
        print("DEBUG put_known_duration_metrics {} {} {} {}".format(metric_name, duration, pipe_id, lang_id))
    metrics.set_namespace(CLOUDWATCH_NAMESPACE)
    metrics.set_dimensions({ "PipeId": pipe_id, "LanguageId": lang_id, "Type": "Durations" })
    metrics.put_metric(metric_name, duration, "Seconds")

# def put_count_metrics(metric_name, metric_value, pipe_id, lang_id, metrics={}):
#     x = {}
# def put_duration_metrics(metric_name, start, end, pipe_id, lang_id, metrics={}):
#     x = {}
# def put_known_duration_metrics(metric_name, duration, pipe_id, lang_id, metrics={}):
#     x = {}

def caption_latest(pipe_id, lang_id):
    start_processtime_dynamo = time.time()
    if DEBUG:
        print("DEBUG caption_latest(pipe_id, lang_id): {}, {}".format(pipe_id, lang_id))
    messages_table = DYNAMO_RESOURCE.Table(DYNAMO_TABLE)
    try:
        response = messages_table.query(
            KeyConditionExpression=Key('id_lang').eq(lang_id),
            ScanIndexForward=False,
            Limit=5,
            IndexName=DYNAMO_INDEX,
            ProjectionExpression='timestamp_created, transcript_resultid, transcript_transcript, transcript_endtime, transcript_starttime',
            FilterExpression=Attr("id_pipe").eq(pipe_id)
            )
    except ClientError as e:
        print("ERROR DynamoDB: %s" % e)
        put_count_metrics('error_lambda', 1, pipe_id, lang_id)
        return False
    if len(response["Items"]) < 1:
        print("ERROR DynamoDB: item list is empty")
        return False
    put_duration_metrics('processtime_dynamo', start_processtime_dynamo, time.time(), pipe_id, lang_id)

    caption_string = False
    caption_latency = False
    if response["Items"][0]:
        caption_string = response["Items"][0]['transcript_transcript']
        caption_latency = float(time.time()) - float(response["Items"][0]['timestamp_created'])
        if float(response["Items"][0]['transcript_endtime']) - float(response["Items"][0]['transcript_starttime']) < float(CAPTION_BUFFER):
            # We need to show the old caption till the buffer time is over
            if DEBUG:
                print("DEBUG newest caption is smaller than CAPTION_BUFFER")
            caption_string = ""
            i = 0
            for item in response["Items"][1:]:
                i = i + 1
                caption_string = item['transcript_transcript'] + "\n" + caption_string
                caption_latency = float(time.time()) - float(item['timestamp_created'])
                if float(item['transcript_endtime']) - float(item['transcript_starttime']) > float(CAPTION_BUFFER):
                    break
        if DEBUG: 
            print("DEBUG caption_string: {}".format(caption_string))
            print("DEBUG caption_latency: {}".format(caption_latency))
        if caption_latency:
            put_known_duration_metrics('latency_caption', caption_latency, pipe_id, lang_id)
    else:
        print("ERROR no current_caption!")
        put_count_metrics('error_lambda', 1, pipe_id, lang_id)
        return False

    return caption_string

def lambda_handler(event, context):
    
    start_processtime_lambda = time.time()
    request = event['Records'][0]['cf']['request'].copy()
    custom_headers = request['origin']['custom'].pop('customHeaders')
    untouched_request = request.copy()
    if request['method'] != 'PUT':
        print("INFO Request Method is: {} skipping...".format(request['method']))
        return untouched_request
    ## Check for environment variables in customHeader
    if not get_environment_variables(custom_headers):
        print("ERROR GLOBALS not set sending request untouched")
        put_count_metrics('error_lambda', 1, 'unknown', 'unknown')
        return untouched_request
    
    try:
        if DEBUG:
            print("DEBUG CF Request: {}".format(request))
        request['headers']['user-agent'][0]['value'] = "AWS Lambda"
        ## Decode .vtt contents
        try: 
            og_body = base64.b64decode(request['body']['data']).decode("utf-8")
        except Exception as e:
            print("ERROR base64decode: %s" % e)
            put_count_metrics('error_lambda', 1, PIPE_ID, 'unknown')
            return untouched_request
        if DEBUG:
            print("DEBUG CF body raw: {}".format(request['body']['data']))
            print("DEBUG CF Body base64 decoded: {}".format(og_body))

        if CAPTION_PASSTHROUGH:
            print("INFO CAPTION_PASSTHROUGH Global is TRUE, skipping autocaptions")
            put_count_metrics('caption_passthrough', 1, PIPE_ID, 'unknown')
            return untouched_request
        
        if CAPTION_REPLACE:
            new_body = []
            caption_detected = False
            for this_line in og_body.splitlines():
                if re.search(r'\d{2,}:\d{2}:\d{2}\.\d{3} --> \d{2,}:\d{2}:\d{2}\.\d{3}', this_line):
                    print("WARNING Caption Detected!")
                    put_count_metrics('caption_detected', 1, PIPE_ID, 'unknown')
                    caption_detected = True
                    break
                else:
                    new_body.append(this_line)
            new_body.append('')
            if caption_detected:
                print("WARNING Caption Scrubbed")
                put_count_metrics('caption_scrubbed', 1, PIPE_ID, 'unknown')
                og_body = "\n".join(new_body)
        else:
            print("WARNING CAPTION_REPLACE Global is FALSE, skipping autocaptions")
            put_count_metrics('caption_skipped', 1, PIPE_ID, 'unknown')
            return untouched_request
        ## CAPTION
        r = re.search(r'channel_(\w{2})_\d{1,}\.vtt', request['uri'])
        if not r: 
            print("ERROR REGEX for lang_id failed, skipping autocaptions")
            put_count_metrics('error_lambda', 1, PIPE_ID, 'unknown')
            return untouched_request
        lang_id = r.group(1)
        if DEBUG: 
            print("DEBUG lang_id: {}".format(lang_id))
        # Get caption text from dynamo
        latest_caption_text = caption_latest(PIPE_ID, lang_id)
        if latest_caption_text == False:
            print("ERROR Caption is False, passthrough unmodified request ")
            put_duration_metrics('processtime_lambda', start_processtime_lambda, time.time(), PIPE_ID, lang_id)
            return untouched_request

        ## Append new caption to vtt file
        try:
            vtt = og_body.splitlines()
            vtt.append("00:00:00.000 --> 1000000:00:00.000 line:13 position:5% align:left size:90%")
            vtt.append(latest_caption_text)
            vtt.append('')
            vtt_file = "\n".join(vtt)
            request['body']['action'] = 'replace'
            request['body']['encoding'] = 'text'
            request['body']['data'] = str(vtt_file)
            if DEBUG:
                print("DEBUG after body: {}".format(request['body']['data']))
            put_duration_metrics('processtime_lambda', start_processtime_lambda, time.time(), PIPE_ID, lang_id)
            return request
        except:
            print("ERROR cannot combine og_body with new captions")
            put_count_metrics('error_lambda', 1, PIPE_ID, lang_id)
            print_exception()
            put_duration_metrics('processtime_lambda', start_processtime_lambda, time.time(), PIPE_ID, lang_id)
            return untouched_request
    except: 
        print("ERROR Outer Lambda Exception")
        put_count_metrics('error_lambda', 1, PIPE_ID, lang_id)
        print_exception()
        put_duration_metrics('processtime_lambda', start_processtime_lambda, time.time(), PIPE_ID, lang_id)
        return untouched_request
    return untouched_request
