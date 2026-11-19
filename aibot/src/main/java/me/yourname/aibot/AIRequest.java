package me.yourname.aibot;

import java.io.*;
import java.net.*;
import org.json.*;

public class AIRequest {
    private static final int CONNECT_TIMEOUT_MS = 10_000;
    private static final int READ_TIMEOUT_MS    = 30_000;

    public static String sendToAI(String userMessage, String apiUrl) {
        try {
            URL url = new URL(apiUrl);
            HttpURLConnection con = (HttpURLConnection) url.openConnection();
            con.setConnectTimeout(CONNECT_TIMEOUT_MS);
            con.setReadTimeout(READ_TIMEOUT_MS);
            con.setRequestMethod("POST");
            con.setRequestProperty("Content-Type", "application/json; utf-8");
            con.setDoOutput(true);

            JSONObject payload = new JSONObject()
                .put("action", "answer")
                .put("query", userMessage);

            try (OutputStream os = con.getOutputStream()) {
                byte[] input = payload.toString().getBytes("utf-8");
                os.write(input, 0, input.length);
            }

            InputStream responseStream = con.getInputStream();
            String responseText = new BufferedReader(new InputStreamReader(responseStream))
                    .lines().reduce("", (acc, line) -> acc + line);

            JSONObject responseJson = new JSONObject(responseText);
            return responseJson.getString("answer");

        } catch (java.net.SocketTimeoutException e) {
            return "AI request timed out. Please try again.";
        } catch (Exception e) {
            e.printStackTrace();
            return "Failed to contact AI.";
        }
    }
}
