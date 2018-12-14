package LambdaPackage;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestStreamHandler;
import com.amazonaws.transcribestreaming.cli.ResponseObject;
import com.amazonaws.transcribestreaming.cli.TranscribeStreamingDemoApp;
import com.google.gson.Gson;
import org.json.simple.JSONObject;
import org.json.simple.parser.JSONParser;
import org.json.simple.parser.ParseException;

import java.io.*;
import java.net.URISyntaxException;
import java.util.concurrent.ExecutionException;


public class Lambda implements RequestStreamHandler {

    @Override
    public void handleRequest( InputStream inputStream, OutputStream outputStream, Context context) {

        JSONParser parser = new JSONParser();

        BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream));
        JSONObject responseJson = new JSONObject();

        String customVocabulary = null;
        JSONObject body;
        String inputUrl = "";

        try {
            JSONObject event = (JSONObject) parser.parse(reader);
            if (event.get("body") != null) {
                body = (JSONObject) event.get("body");
            }
            System.out.println(inputUrl);

            TranscribeStreamingDemoApp app = new TranscribeStreamingDemoApp();

            ResponseObject object =  app.getTextFromURL(inputUrl, customVocabulary);
            Gson gson = new Gson();
            String response = gson.toJson(object);

            JSONObject responseBody = new JSONObject();
            JSONObject headerJson = new JSONObject();

            responseJson.put("statusCode", 200);
            responseJson.put("headers", headerJson);
            responseJson.put("body", response);

        } catch (ParseException pex) {
            responseJson.put("statusCode", 400);
            responseJson.put("exception", pex);
        } catch (IOException e) {
            e.printStackTrace();
        } catch (InterruptedException e) {
            e.printStackTrace();
        } catch (ExecutionException e) {
            e.printStackTrace();
        } catch (URISyntaxException e) {
            e.printStackTrace();
        }

        try (OutputStreamWriter writer = new OutputStreamWriter(outputStream, "UTF-8")) {
            writer.write(responseJson.toString());
            writer.close();
        }catch(IOException e){
            e.printStackTrace();
        }
    }
}

