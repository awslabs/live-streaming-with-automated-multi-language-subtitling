# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# start with long-term-support version of the node.js with alpine os docker image
FROM node:lts-alpine

# create the application directory
RUN mkdir /transcriber
WORKDIR /transcriber

# Install Build Dependencies for the docker image. 
RUN apk add --no-cache --virtual .gyp \
        python3 \
        make \
        g++ \
        ffmpeg

# install application dependencies
RUN npm install aws-sdk aws-signature-v4 query-string sleep websocket bcrypt @aws-sdk/client-transcribe-streaming@gamma @aws-sdk/eventstream-marshaller @aws-sdk/util-utf8-node 

# copy the application files
COPY transcribe-to-dynamo-withSDK.js healthcheck.py run.sh ./

RUN ["chmod", "+x", "run.sh"]

# Expose the port for UDP
EXPOSE 7950

# Run this inside the docker container
# CMD ./ffmpeg -re -i video.mp4 -f mpegts udp://localhost:7950

# run it when the container starts -- requires environment vars
CMD sh run.sh
