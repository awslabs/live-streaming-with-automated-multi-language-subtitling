#!/bin/bash
function_name=LAMBDA_ARN

mkdir deploy
cp lambda_function.py deploy/
cp ffmpeg deploy/
cp ffprobe deploy/
cp src/audiomagic.py deploy/
cp -r venv/lib/python3.6/site-packages/* deploy/

cd deploy ; zip -r -X ../deploy.zip . * ; cd ..
aws lambda update-function-code --function-name $function_name --zip-file fileb://deploy.zip
