# Run health check python webserver for load balancer
# Runs on port 8080
nohup python3 healthcheck.py &

# Run AWS Transcriber code in infinite loop
while :
do
  ffmpeg -i udp://127.0.0.1:7950 -tune zerolatency -f wav -ar 16000 -ac 1 - 2>/dev/null | node transcribe-to-dynamo-withSDK.js -
  sleep 3
done
