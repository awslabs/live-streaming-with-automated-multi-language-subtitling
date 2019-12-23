# ==================================================================================
# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# ==================================================================================
#
# lambda_function.py
# by: Eddie Goynes
# 
# Purpose: Proof of concept showing caption insertion into a MediaLive MediaPackage stream using 
#          AWS Machine learning services. AWS Transcribe, AWS Polly and AWS Translate. 
#          Services used include S3 with versioning, cloud watch events, lambda, and CloudFront.

# Change Log:
#          11/20/2018: Initial version
#
# ==================================================================================

import os
import sys
import json
import random
import datetime
import requests
import boto3
import botocore
import uuid
import string 
import collections
from requests.auth import HTTPDigestAuth
from multiprocessing.pool import ThreadPool
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from botocore.config import Config

# Used to surpress warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

patch_all()

# Logging
# EXCEPTION for exceptions
TRANSCRIBE_LAMBDA_ARN = os.environ.get('transcribeLambdaARN')

# Used for debugging purposes.
DEBUG=False
# Threading
POOL = ThreadPool(processes=16)
TMP_DIR = '/tmp/'
# Global Bucket for temp storage
BUCKET_NAME = ""
NAME_MODIFIER = '_416x234_200k'
# Caption languages getting generated.
LANGUAGES = []

# Languages supported by Amazon Translate
LANGUAGE_CODES = {
    'ar': 'Arabic',
    'zh': 'Chinese Simplified',
    'zh-TW': 'Chinese Traditional',
    'cs': 'Czech',
    'da': 'Danish',
    'nl': 'Dutch',
    'en': 'English',
    'fi': 'Finnish',
    'fr': 'French',
    'de': 'German',
    'he': 'Hebrew',
    'id': 'Indonesian',
    'it': 'Italian',
    'ja': 'Japanese',
    'ko': 'Korean',
    'pl': 'Polish',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'es': 'Spanish',
    'sv': 'Swedish',
    'tr': 'Turkish'
}


# ==================================================================================
# Function: get_mediapackage_password
# Purpose: MediaPackage Password is stored in SSM. I look there to get it in my code. 
# Parameters: 
#               None
# ==================================================================================
def get_mediapackage_password(mediaPackageUsername):
    # SSM manager using the outputChannelUsername to get the MediaPackage Password.
    try: 
        client = boto3.client('ssm')
        res = client.get_parameter(Name=mediaPackageUsername)
        mediaPackagePassword = res['Parameter']['Value']
    except Exception as e:
        print("EXCEPTION: Unable to get MediaPackage password from SSM - " + str(e))

    return mediaPackagePassword


# ==================================================================================
# Function: send_to_mediapackage
# Purpose: Uses WebDav with authentication to send files into MediaPackage
# Parameters: 
#               filename - Name of the file you want to be sent to MediaPackage.
#               data - binary data of your file
# ==================================================================================
def send_to_mediapackage(filename, data, pipe_number):
    if pipe_number == 0:
        outputChannelUrl = os.environ['mediaPackageUrlPipe0']
        outputChannelUsername = os.environ['mediaPackageUsernamePipe0']
    else:
        outputChannelUrl = os.environ['mediaPackageUrlPipe1']
        outputChannelUsername = os.environ['mediaPackageUsernamePipe1']

    outputChannelPassword = get_mediapackage_password(outputChannelUsername)
    outputChannelUrl = outputChannelUrl.replace('/channel', '') + "/" + filename
    try:
        response = requests.put(outputChannelUrl, auth=HTTPDigestAuth(outputChannelUsername,outputChannelPassword), data=data, verify=False)
    except Exception as e:
        print("TEST: Exception Pipe number is: " + str(pipe_number))
        print("Output channel url: " + outputChannelUrl)
        print("Output channel username: " + outputChannelUsername)
        print("Output channel Password: " + outputChannelPassword)

        print(str(e))

    # If the response has a 401 error resend the file. 
    if '401' in str(response):
        print('EXCEPTION: Got a 401 response from MediaPackage sending again. ' + str(filename))
        send_to_mediapackage(filename, data, pipe_number)

# ==================================================================================
# Function: send_file_to_mediapackage
# Purpose: Wrapper around send_to_mediapackage to send files to MediaPackage
# Parameters: 
#               path - Local path of your file
#               remove_file - (Boolean) Do you want to delete your file
# ==================================================================================
def send_file_to_mediapackage(path, remove_file, pipe_number):
    filename = path.split('/')[-1]
    with open(path, 'rb') as f:
        data = f.read()
        send_to_mediapackage(filename, data, pipe_number)
    if remove_file:
        os.remove(path)
    return True


# ==================================================================================
# Function: make_random_string
# Purpose: Used as a GUID for creating local files.
# Parameters: 
#               none
# ==================================================================================
def make_random_string():
    return ''.join([random.choice(string.ascii_letters + string.digits) for n in range(32)])

# ==================================================================================
# Function: upload_file_s3
# Purpose: Used to upload files to the bucket created by CloudFormation.
# Parameters: 
#               path - Path to file to upload
#               name - s3 key name
# ==================================================================================
def upload_file_s3(path, name):
    s3 = boto3.resource('s3')
    with open(path, 'rb') as data:
        try:
            s3.Bucket(BUCKET_NAME).put_object(Key=name , Body=data)
        except Exception as e:
            print("EXCEPTION: When uploading file to S3 " + str(e))
            return False
    return True

# ==================================================================================
# Function: get_text_from_transcribe
# Purpose: Calls API of Transcribe Streaming Lambda. Gets text from TS Segment.
# Parameters:
#               ts_file_path - Path to ts segment
# ==================================================================================
def get_text_from_transcribe(ts_file_path):

    # Check to make sure that TS file exists
    if not os.path.isfile(ts_file_path):
        print("EXCEPTION: ts file doesn't exist to make PCM file for Transcribe : " + ts_file_path)
        sys.exit()

    # Use ffmpeg to create PCM audio file for Transcribe
    output_pcm = TMP_DIR + str(make_random_string()) + '.pcm'
    cmd = './ffmpeg -hide_banner -nostats -loglevel error -y -i ' + ts_file_path + ' -vn -f s16le -acodec pcm_s16le -ac 1 -ar 16000 ' + output_pcm + '  > /dev/null 2>&1 '
    wav_ffmpeg_response = os.popen(cmd).read()

    # After FFMPEG send the file into S3 and generate presigned URL.
    s3_key = 'audio_files/' + output_pcm.split('/')[-1]
    upload_file_s3(output_pcm, s3_key)
    presigned_url = get_presigned_url_s3(s3_key)

    # Remove the file I just uploaded to s3
    os.remove(output_pcm)

    # Use Presigned url with the API for security.
    client = boto3.client('lambda') 
    try:
        response = client.invoke(FunctionName=TRANSCRIBE_LAMBDA_ARN, Payload=json.dumps({'body' : presigned_url}))
        json_res = json.loads(json.loads(response['Payload'].read())['body'])
    
        # Get Text
        text = json_res['transcript']
        print("DEBUG: Text returned from Transcribe Streaming is: " + text)

    except Exception as e:
        print("EXCEPTION: AWS Transcribe Streaming is throttling! Putting empty subtitle into stream. Increase Transcribe Streaming Limits: " + str(e))
        # Set the text to nothing. 
        text = ""

    return text


# ==================================================================================
# Function: segment_duration_from_child_manifest
# Purpose: Gets TS segment duration from a child manifest string.
# Parameters: 
#               child_manifest - String of the child manifest file.
# ==================================================================================
def segment_duration_from_child_manifest(child_manifest):
    lines = child_manifest.split('\n')[:-1]
    # Example string #EXTINF:6.00600,
    for line in lines:
        if '#EXTINF:' in line:
            seconds = int(float(line.replace('#EXTINF:', '').replace(',','')))
            return seconds
    # Default to 6 if no segment length in manifest
    return 6
    
# ==================================================================================
# Function: get_vtt_time_stamp
# Purpose: Gets Prestation Time Stamp (PTS) values and creates a VTT timestamp.
# Parameters: 
#               ts_file_path - Path to ts segment
# ==================================================================================
def get_vtt_time_stamp(ts_file_path, child_manifest):
    cmd = './ffprobe -v quiet -select_streams v:0 -show_entries format=duration:stream=start_pts -of default=noprint_wrappers=1 ' + ts_file_path 
    output = os.popen(cmd).read()

    # Get Start PTS and Duration (Presentation Time Stamp PTS is used to know where to insert the captions)
    for line in output.split('\n'):
        if 'start_pts' in line:
            start_time_sec = float(line.split('=')[-1]) / 90000
        # elif 'duration' in line:
        #     duration = int(float(line.split('=')[-1]))

    # Offset because of the MPEGTS:18000. Video is offset two seconds in the future of the captions.
    start_time_sec = start_time_sec - 2
    duration = segment_duration_from_child_manifest(child_manifest)

    return seconds_to_vtt_timestamp(start_time_sec) + " --> " +  seconds_to_vtt_timestamp(start_time_sec + int(duration))

# ==================================================================================
# Function: seconds_to_vtt_timestamp
# Purpose: Helper function for get_vtt_time_stamp
# Parameters: 
#               input_seconds - PTS value in seconds
# ==================================================================================
def seconds_to_vtt_timestamp(input_seconds):
    hours = str(int(input_seconds / 3600)).zfill(2)
    minutes = str(int((input_seconds % 3600) / 60)).zfill(2)
    seconds = str(int((input_seconds % 3600) % 60)).zfill(2)
    micro_seconds = str(round(input_seconds % 1, 3)).replace('0.','').ljust(3,'0')

    return ":".join([hours, minutes, seconds]) + '.'  + str(micro_seconds)


# ==================================================================================
# Function: make_vtt_file
# Purpose: Creates a WebVTT caption file
# Parameters: 
#               child - Child TS file manifest string
#               ts_file_path - path to the ts segment
#               text - Text to be put into the WebVTT caption file.
#               lang - Language that you want the WebVTT file to be in.
# ==================================================================================
def make_vtt_file(child, ts_file_path, text, lang):
    segment_name = ts_file_path.split('/')[-1]
    # Get the time that I need to put the caption in. 
    # optimization. I could do this just once. Instead of once for each language.
    vtt_timestamp = get_vtt_time_stamp(ts_file_path, child)

    # Now that I have the last TS file and the program date time I can make a VTT file.
    vtt = ['WEBVTT	\nX-TIMESTAMP-MAP=MPEGTS:180000,LOCAL:00:00:00.000','']
    # Make first time
    vtt.append(vtt_timestamp)
    vtt.append(text)
    vtt.append('')

    # Join the file and return it.
    name = segment_name.replace('.ts', '.vtt').replace(NAME_MODIFIER + '_', '_caption'+lang+'_')

    # Return tuple with the name and the file
    vtt_file = "\n".join(vtt).encode("utf-8")

    # For debugging
    if DEBUG:
        print("My VTT File is \n" + str(vtt_file)) 

    return (name, vtt_file)
 
# ==================================================================================
# Function: make_vtt_manifest
# Purpose: Creates a VTT caption manifest file
# Parameters: 
#               child_manifest - Child TS file manifest string
#               lang - Language that you want the WebVTT file to be in.
# ==================================================================================
def make_vtt_manifest(child_manifest, lang):
    return child_manifest.replace('.ts', '.vtt').replace(NAME_MODIFIER + '_', '_caption'+lang+'_')

# ==================================================================================
# Function: make_audio_manifest
# Purpose: Creates an alternate audio manifest
# Parameters: 
#               child_manifest - Child TS file manifest string
#               lang - Language that you want the WebVTT file to be in.
# ==================================================================================
def make_audio_manifest(child_manifest, lang):
    return child_manifest.replace(NAME_MODIFIER + '_', '_'+lang+'_')


# ==================================================================================
# Function: get_last_segment_name
# Purpose: Gets the last line from a Child Manifest file.
# Parameters: 
#               child_manifest - Child TS file manifest string
# ==================================================================================
def get_last_segment_name(child_manifest):
    child_manifest = child_manifest.split('\n')
    child_manifest.reverse()
    for x in child_manifest:
        if '.ts' in x:
            segment_name = x
            return segment_name
    return "ERROR"

# ==================================================================================
# Function: get_presigned_url_s3
# Purpose: Signs an S3 URL for a GET request
# Parameters: 
#               s3_key - Key of the file you want in S3.
# ==================================================================================
def get_presigned_url_s3(s3_key):
    s3 = boto3.client('s3', config = Config(signature_version = 's3v4', s3={'addressing_style': 'virtual'}))
    try:
        url = s3.generate_presigned_url('get_object', Params = {'Bucket': BUCKET_NAME, 'Key':s3_key}, ExpiresIn = 1200)
    except Exception as e:
        print("EXCEPTION: When getting presigned url > " + str(e))

    return url 

# ==================================================================================
# Function: download_file_from_s3
# Purpose: Downloads file to /tmp/ directory in Lambda
# Parameters: 
#               s3_key - Key of the file you want in S3.
#               bucket_name - Bucket you want the file from.
# ==================================================================================
def download_file_from_s3(s3_key, bucket_name):
    output_dir =  TMP_DIR + s3_key.split('/')[-1]
    s3 = boto3.client('s3')
    # Used to wait for the S3 object to exist
    waiter = s3.get_waiter('object_exists')
    try:
        # Used to wait for the S3 object to exist
        waiter.wait(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            WaiterConfig={
                'Delay': 1,
                'MaxAttempts': 6
            }
        )
        s3.download_file(bucket_name, s3_key, output_dir)
    # except botocore.exceptions.ClientError as e:
    except Exception as e:
        print("EXCEPTION: Download file from s3 object does not exist " + str(s3_key)+" ." + str(e))
        # Return from program
        sys.exit()


    return output_dir

# ==================================================================================
# Function: send_ts_to_mediapackage
# Purpose: Downloads file to /tmp/ directory in Lambda
# Parameters: 
#               ts_file_path - Local path of your ts video file.
#               segment_name - Name of the TS file segment
#               child_manifest - string containing the child manifest
#               using_polly - (Boolean) If you are using Polly
# ==================================================================================
def send_ts_to_mediapackage(ts_file_path, segment_name, child_manifest, using_polly, pipe_number):
    if using_polly:
        video_file = TMP_DIR + segment_name
        audio_file = TMP_DIR + segment_name.replace('_480p30', '_english')

        # Split Audio and Video TS and send them seperatly.
        os.popen('./ffmpeg -y -hide_banner -nostats -i  "' + ts_file_path + '" -copyts -map 0:a -acodec copy "'+ audio_file +'" -map 0:v -vcodec copy "'+ video_file +'" > /dev/null 2>&1 ').read()

        print("checking to see if file exists " + video_file + ' ' + str(os.path.exists(video_file)))
        print("checking to see if file exists " + audio_file + ' ' + str(os.path.exists(audio_file)))

        # Upload to S3 for test
        send_file_to_mediapackage(video_file, False, pipe_number)
        send_file_to_mediapackage(audio_file, False, pipe_number)

        # Make sure to send manifest for audio file.
        manifest =  make_audio_manifest(child_manifest, 'english')
        filename = 'channel_english.m3u8'
        send_to_mediapackage(filename, manifest, pipe_number)

    else:
        return send_file_to_mediapackage(ts_file_path, False, pipe_number)
    

def get_s3_file(s3_key):
    if DEBUG:
        print("The S3_key is " + s3_key)
    try:
        s3 = boto3.client('s3')
        # Used to wait for the S3 object to exist
        waiter = s3.get_waiter('object_exists')
        waiter.wait(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            WaiterConfig={
                'Delay': 1,
                'MaxAttempts': 6
            })
        response = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        s3object = response['Body'].read()
    except Exception as e:
        print('EXCEPTION: Getting file called '+s3_key+' from S3 exception: '  + str(e))
    return s3object

def get_s3_file_versionid(s3_key, versionid):
    try:
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key, VersionId=versionid)
        s3object = response['Body'].read().decode('utf-8') 
    except Exception as e:
        print('EXCEPTION: When getting file from S3 > ' + str(e))

    return s3object

# Send TS file within manifest into the 
def send_ts_file_and_manifest(s3_key, s3_version, pipe_number):

    # Get manifest
    manifest_name = s3_key.split('/')[-1]
    manifest = get_s3_file_versionid(s3_key, s3_version)
    # Get TS filename
    tsfile_name = manifest.split('\n')[-2]

    # Get ts file from S3
    ts_file_s3_key = s3_key.split('/')[0] + '/' + tsfile_name
    tsfile = get_s3_file(ts_file_s3_key)

    # Send both files into MediaPackage
    send_to_mediapackage(tsfile_name, tsfile, pipe_number)
    send_to_mediapackage(manifest_name, manifest, pipe_number)

    return True

# Gets the TS file from S3. Then it sends it into MediaPackage with authenticated WebDav.
def send_s3_file_to_mediapackage(s3_key):
    # Get file from S3 bucket
    s3object = get_s3_file(s3_key)
    # Get the name of the file.
    file_name = s3_key.split('/')[-1]
    # Send TS file onto MediaPackage
    send_to_mediapackage(file_name, s3object)

    return True


def send_master_manifest_to_mediapackage(s3_key, s3_version, pipe_number):
    # Get S3 manifest file and attach the captions onto the end of the manifest.
    original_manifest = get_s3_file_versionid(s3_key, s3_version)

    manifest_name = 'channel.m3u8'

    if DEBUG:
        print("Revieved master manifest " + s3_key)
        print("Languages that are used are " + str(LANGUAGES))
    
    # Create Caption Language Portion of the manifest. 
    add_to_manifest = ""

    for lang in LANGUAGES:
        lang_name = LANGUAGE_CODES[lang]
        add_to_manifest += '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="'+lang_name+'",DEFAULT=YES,AUTOSELECT=YES,FORCED=NO,LANGUAGE="'+lang+'",URI="channel_caption'+lang+'.m3u8"\n'

    master = original_manifest + add_to_manifest

    # Send the master manifest into MediaPackage
    if DEBUG:
        print("Sending Master Manifest " + master)

    send_to_mediapackage(manifest_name, master, pipe_number)
    return master




# ==================================================================================
# Function: make_all_transcriptions
# Purpose: Translates text with Amazon Translate in parallel.
# Parameters: 
#               text - string of text you are translating
#               languages - List containing language codes that you want.
# ==================================================================================
def make_all_transcriptions(text, languages):
    source_lang = 'en'
    transcripts = {}
    # Start all the threads
    for lang in languages:
        transcripts[lang] = POOL.apply_async(get_transcript, (source_lang, lang, text)) 
    # Get the results
    for lang in languages:  
        transcripts[lang] = transcripts[lang].get()

    return transcripts

# ==================================================================================
# Function: get_transcript
# Purpose: Helper function that Translates text with Amazon Translate
# Parameters: 
#               source_lang - Source code (Example: en)
#               target_lang - Desntination code (Example: es)
#               text - string of text you are translating
# ==================================================================================
def get_transcript(source_lang, target_lang, text):
    try:
        translate = boto3.client('translate')
        translation = translate.translate_text(Text=text, SourceLanguageCode=source_lang, TargetLanguageCode=target_lang)['TranslatedText']
    except:
        return "" #There is no text. Nothing is being said return an empty string. 
    return translation

# ==================================================================================
# Function: send_all_vtt_files_and_manifests
# Purpose: Sends all WebVTT manifests and files.
# Parameters: 
#               ts_file_path - Source code (Example: en)
#               child_manifest - Desntination code (Example: es)
#               transcripts - string of text you are translating
#               languages - A list of the languages 
# ==================================================================================
def send_all_vtt_files_and_manifests(ts_file_path, child_manifest, transcripts, languages, pipe_number):
    threads = []

    for lang in languages:
        threads.append(POOL.apply_async(send_vtt_file_and_manifest, (lang, ts_file_path, child_manifest, transcripts, pipe_number)))
    # Get the responses.
    results = [x.get() for x in threads]
    return results


# ==================================================================================
# Function: send_vtt_file_and_manifest
# Purpose: Helper function that sends a WebVTT file and Manifest.
# Parameters: 
#               lang - Source code (Example: en)
#               ts_file_path - path to local ts video file
#               child_manifest - string of the child manifest
#               transcripts - list of transcripts of each language
# ==================================================================================
def send_vtt_file_and_manifest(lang, ts_file_path, child_manifest, transcripts, pipe_number):
    # Create Simple VTT File and send that into MediaPackage         
    vtt_segment_name, vtt_file = make_vtt_file(child_manifest, ts_file_path, str(transcripts[lang]), lang)

    # Put Vtt segment to mediapackage
    send_to_mediapackage(vtt_segment_name, vtt_file, pipe_number)

    # Send VTT manifest to MediaPackage
    send_to_mediapackage('channel_caption'+ lang +'.m3u8', make_vtt_manifest(child_manifest, lang), pipe_number)
    return True


# ==================================================================================
# Function: send_vtt_file_and_manifest
# Purpose: Helper function that sends a WebVTT file and Manifest.
# Parameters:
#               child_name - name of the child manifest
#               child_manifest - string that contains the child video manifest
# ==================================================================================
def caption_generation(child_name, child_manifest, pipe_number):
    using_polly = False

    # Download TS Segment from S3
    ts_segment_name = get_last_segment_name(child_manifest)

    if '#EXT-X-ENDLIST' in ts_segment_name:
        # MediaLive channel was restarted skip this segment.
        print("#EXT-X-ENDLIST found exiting lambda.")
        sys.exit()

    # Download the file from S3. 
    if pipe_number == 1:
        base_name = 'livestream_pipe1/'
    else:
        base_name = 'livestream_pipe0/'

    print("GETTING: Downloading file from S3 for captions trying to get this file : " + base_name + ts_segment_name )
    ts_file_path = download_file_from_s3(base_name + ts_segment_name, BUCKET_NAME)

    # Push TS segment to MediaPackage
    # If using Polly is True Audio and Video will be split for an english only track.
    send_ts_to_mediapackage(ts_file_path, ts_segment_name, child_manifest, using_polly, pipe_number)

    print("TRANSCRIBE: Getting text from transcribe ")
    # Use TS with FFMPEG to make captions
    text = get_text_from_transcribe(ts_file_path)

    if DEBUG:
        print("Caption text is: " + text)
    # Check if no text. Nothing is being said. Send empty VTT files.
    # Send all the VTT files then the VTT manifests into MediaPackage
    transcripts = make_all_transcriptions(text, LANGUAGES)

    # Thread this function
    send_all_vtt_files_and_manifests(ts_file_path, child_manifest, transcripts, LANGUAGES, pipe_number)

    # Send the Child manifest to MediaPackage
    send_to_mediapackage(child_name, child_manifest, pipe_number)

    # Last Clean Up things
    # Remove the TS file that I have been using. 
    try:
        os.remove(ts_file_path)
    except Exception as e:
        print("TS file was not there " + ts_file_path)


    return True
 

# ==================================================================================
# Function: lambda_handler
# Purpose: entry point for the system.
# Parameters:
#               event - from lambda
#               context - from lambda
# ==================================================================================
def lambda_handler(event, context):
    child_name = 'channel_name.m3u8'

    # Get bucket name
    global BUCKET_NAME 
    BUCKET_NAME = event['Records'][0]['s3']['bucket']['name']

    global LANGUAGES
    # Make sure that the languages the customer entered are supported. And remove duplicate langauges from input.
    LANGUAGES = [x.strip() for x in str(os.environ['captionLanguages']).split(',')]
    LANGUAGES = [lang for lang in LANGUAGES if lang in LANGUAGE_CODES.keys()]
    LANGUAGES = list(collections.OrderedDict.fromkeys(LANGUAGES))

    # S3 trigger is setup to only allow files that are ending in .m3u8 to pass into this lambda. 
    # Get the name of the file that was sent into S3. 
    s3_key = event["Records"][0]["s3"]["object"]["key"]
    s3_version = event['Records'][0]['s3']['object']['versionId']

    # Figure out if we are working with pipe0 or pipe1 for MediaLive output, and MediaPackage failover.
    if "pipe1" in s3_key:
        # We are working with pipe0 set pipe number to 1
        pipe_number = 1 
    else:
        pipe_number = 0


    # Check if the manifest is a master manifest
    if 'channel.m3u8' in s3_key:
        # It is a master manifest. Send the master manifest. 
        send_master_manifest_to_mediapackage(s3_key, s3_version, pipe_number)
    
    # Check if the file is a child manifest file.
    elif '.m3u8' in s3_key:
        print("DEBUG: Languages being used " + str(LANGUAGES))
        # Check to see if it is the _416x234_200k rendition of the video. This is what I will use for caption generation.
        if NAME_MODIFIER in s3_key:
            # Get child manifest
            manifest_file = get_s3_file_versionid(s3_key, s3_version)
            # Get child name
            manifest_name = s3_key.split('/')[-1]

            caption_generation(manifest_name, manifest_file, pipe_number)

        else: 
            # Send the TS file within the manifest.
            send_ts_file_and_manifest(s3_key, s3_version, pipe_number)

    return True


def main():
    pass

if __name__ == '__main__':
    main()

