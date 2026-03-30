import express from "express";
import { createServer as createViteServer } from "vite";
import cors from "cors";
import axios from "axios";
import { GoogleGenAI, ThinkingLevel } from "@google/genai";
import fs from "fs";
import path from "path";
import https from "https";

// --- Axios Instance with IPv4 forcing ---
// Render環境での GitHub API への ETIMEDOUT を回避するため IPv4 を強制します
const httpsAgent = new https.Agent({ family: 4 });
const axiosInstance = axios.create({
  httpsAgent,
  timeout: 30000, // 30秒タイムアウト
} as any);

// --- Logging Helper ---
function writeErrorLog(message: string, error?: any) {
  try {
    const logsDir = path.join(process.cwd(), "logs");
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }

    const now = new Date();
    const timestamp = now.getFullYear().toString() +
      (now.getMonth() + 1).toString().padStart(2, '0') +
      now.getDate().toString().padStart(2, '0') + "_" +
      now.getHours().toString().padStart(2, '0') +
      now.getMinutes().toString().padStart(2, '0') +
      now.getSeconds().toString().padStart(2, '0');

    const logFileName = `error_${timestamp}.log`;
    const logFilePath = path.join(logsDir, logFileName);

    let logContent = `Timestamp: ${now.toISOString()}\n`;
    logContent += `Message: ${message}\n`;

    if (error) {
      if (error.message) {
        logContent += `Error Message: ${error.message}\n`;
      }
      if (error.response) {
        logContent += `Response Status: ${error.response.status}\n`;
        // GitHub API responses can be large, but usually contain useful error messages
        logContent += `Response Data: ${JSON.stringify(error.response.data, null, 2)}\n`;
      }
      if (error.stack) {
        logContent += `Stack Trace:\n${error.stack}\n`;
      }
      
      // Axios config might contain Authorization headers, so we MUST sanitize it
      if (error.config) {
        const sanitizedConfig = {
          url: error.config.url,
          method: error.config.method,
          headers: { ...error.config.headers }
        };
        // Remove sensitive headers
        if (sanitizedConfig.headers) {
          delete sanitizedConfig.headers.Authorization;
          delete sanitizedConfig.headers.authorization;
        }
        logContent += `Request Info (Sanitized): ${JSON.stringify(sanitizedConfig, null, 2)}\n`;
      }
    }

    fs.writeFileSync(logFilePath, logContent);
    console.error(`[FATAL] Error details written to logs/${logFileName}`);
  } catch (logErr) {
    console.error("Failed to write error log:", logErr);
  }
}

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(cors());
  app.use(express.json());

  // 必須環境変数チェック（未設定時はエラー終了）
  const requiredEnvVars = ["APP_PASSCODE", "REPO_ACCESS_TOKEN", "REPO_OWNER", "REPO_NAME", "API_KEY01"];
  const missingVars = requiredEnvVars.filter(key => !process.env[key]);
  
  if (missingVars.length > 0) {
    const msg = `[FATAL] 以下の環境変数が設定されていません: ${missingVars.join(", ")}`;
    console.error(msg);
    writeErrorLog(msg);
    process.exit(1);
  }

  // --- 認証 API ---
  app.post("/api/auth", (req, res) => {
    const { passcode } = req.body;
    const correctPasscode = process.env.APP_PASSCODE;
    if (passcode === correctPasscode) {
      res.json({ success: true });
    } else {
      res.status(401).json({ success: false, message: "パスコードが間違っています" });
    }
  });

  // --- GitHub API ヘルパー関数 ---
  const getGithubHeaders = () => {
    const token = process.env.REPO_ACCESS_TOKEN;
    if (!token) throw new Error("REPO_ACCESS_TOKEN is not set");
    return {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github.v3+json",
      "User-Agent": "auto-shogi-report-webui",
    };
  };

  const getGithubApiUrl = (path: string) => {
    const owner = process.env.REPO_OWNER;
    const repo = process.env.REPO_NAME;
    // Render環境では RENDER_GIT_BRANCH が自動で設定されます。ローカルや未設定の場合は main をデフォルトにします。
    const branch = process.env.RENDER_GIT_BRANCH || process.env.REPO_BRANCH || "main";
    if (!owner || !repo) throw new Error("REPO_OWNER or REPO_NAME is not set");
    
    // パス部分をエンコード
    const encodedPath = path.split('/').map(segment => encodeURIComponent(segment)).join('/');
    return `https://api.github.com/repos/${owner}/${repo}/contents/${encodedPath}?ref=${branch}`;
  };

  // --- GitHub API エンドポイント ---
  // 1. カテゴリ内のディレクトリ一覧取得
  app.get("/api/github/categories/:category", async (req, res) => {
    try {
      const { category } = req.params;
      const url = getGithubApiUrl(category);
      const response = await axiosInstance.get(url, { headers: getGithubHeaders() });
      const data = response.data as any[];

      let dirs = data
        .filter((item: any) => item.type === "dir")
        .map((item: any) => item.name);

      // tempカテゴリの場合、rate_trgから始まるディレクトリを除外
      if (category === "temp") {
        dirs = dirs.filter((name: string) => !name.startsWith("rate_trg"));
      }

      res.json({ dirs });
    } catch (error: any) {
      const errorMsg = "Failed to fetch directories";
      console.error(`Error fetching categories (${req.params.category}):`, error.response?.data || error.message);
      writeErrorLog(`Error in /api/github/categories/${req.params.category}`, error);
      res.status(500).json({ error: errorMsg });
    }
  });

  // 2. battle_id一覧取得
  app.get("/api/github/battles/:category/:subCategory", async (req, res) => {
    try {
      const { category, subCategory } = req.params;
      const url = getGithubApiUrl(`${category}/${subCategory}`);
      const response = await axiosInstance.get(url, { headers: getGithubHeaders() });
      const data = response.data as any[];

      const battles = data
        .filter((item: any) => item.type === "dir")
        .map((item: any) => item.name);

      res.json({ battles });
    } catch (error: any) {
      const errorMsg = "Failed to fetch battles";
      console.error(`Error fetching battles (${req.params.category}/${req.params.subCategory}):`, error.response?.data || error.message);
      writeErrorLog(`Error in /api/github/battles/${req.params.category}/${req.params.subCategory}`, error);
      res.status(500).json({ error: errorMsg });
    }
  });

  // 3. レポート詳細取得 (画像、テキスト)
  app.get("/api/github/report/:category/:subCategory/:battleId", async (req, res) => {
    try {
      const { category, subCategory, battleId } = req.params;
      const basePath = `${category}/${subCategory}/${battleId}`;
      const headers = getGithubHeaders();

      // response.txt の取得
      let responseText = "";
      try {
        console.log(`[DEBUG] Fetching response.txt from: ${getGithubApiUrl(`${basePath}/response.txt`)}`);
        const txtRes = await axiosInstance.get(getGithubApiUrl(`${basePath}/response.txt`), { headers });
        const data = txtRes.data as any;
        responseText = Buffer.from(data.content, "base64").toString("utf-8");
        console.log(`[DEBUG] response.txt fetched successfully. Length: ${responseText.length}`);
      } catch (e: any) {
        console.warn(`[ERROR] response.txt not found or error. Status: ${e.response?.status}, Message: ${e.message}`);
      }

      // raw.kif の取得 (チャットのコンテキスト用)
      let rawKif = "";
      try {
        const kifRes = await axiosInstance.get(getGithubApiUrl(`${basePath}/raw.kif`), { headers });
        const data = kifRes.data as any;
        rawKif = Buffer.from(data.content, "base64").toString("utf-8");
      } catch (e) {
        console.warn("raw.kif not found or error:", e);
      }

      // local_report.json の取得 (re_url用)
      let reUrl = "";
      try {
        const jsonRes = await axiosInstance.get(getGithubApiUrl(`${basePath}/local_report.json`), { headers });
        const data = jsonRes.data as any;
        const jsonContent = Buffer.from(data.content, "base64").toString("utf-8");
        const reportData = JSON.parse(jsonContent);
        reUrl = reportData["各対局の振り返り"]?.[battleId]?.["解析URL"] || "";
      } catch (e) {
        console.warn("local_report.json not found or error:", e);
      }

      // banmen_all_full.png の取得 (RawデータからBase64へ変換)
      let banmenImageUrl = "";
      try {
        let imagePath = `${basePath}/banmen_all_full.png`; // battle_id 直下を試す
        let imgRes: any;

        try {
          console.log(`[DEBUG] Fetching image info from: ${getGithubApiUrl(imagePath)}`);
          imgRes = await axiosInstance.get(getGithubApiUrl(imagePath), { headers });
        } catch (e: any) {
          if (e.response?.status === 404) {
            // battle_id 直下にない場合は、subCategory 直下を試す (例: temp/trg_.../banmen_all_full.png)
            console.log(`[DEBUG] Image not found in battle_id dir. Trying subCategory dir...`);
            imagePath = `${category}/${subCategory}/banmen_all_full.png`;
            console.log(`[DEBUG] Fetching image info from fallback: ${getGithubApiUrl(imagePath)}`);
            imgRes = await axiosInstance.get(getGithubApiUrl(imagePath), { headers });
          } else {
            throw e; // 404以外のエラーはそのまま投げる
          }
        }

        const data = imgRes.data as any;
        console.log(`[DEBUG] Image info fetched successfully. Size: ${data.size} bytes, Download URL: ${data.download_url ? 'Exists' : 'None'}`);

        if (data.download_url) {
          console.log(`[DEBUG] Fetching raw image data with Accept: application/vnd.github.v3.raw`);
          const rawImgRes = await axiosInstance.get(getGithubApiUrl(imagePath), {
            headers: {
              Authorization: `Bearer ${process.env.REPO_ACCESS_TOKEN}`,
              Accept: 'application/vnd.github.v3.raw'
            },
            responseType: 'arraybuffer'
          });

          console.log(`[DEBUG] Raw image data fetched. Buffer length: ${(rawImgRes.data as any).byteLength}`);
          const base64 = Buffer.from(rawImgRes.data as any).toString('base64');
          banmenImageUrl = `data:image/png;base64,${base64}`;
          console.log(`[DEBUG] Image converted to base64 successfully. String length: ${banmenImageUrl.length}`);
        } else {
          console.warn(`[DEBUG] No download_url found in the GitHub API response for image.`);
        }
      } catch (e: any) {
        console.error(`[ERROR] Failed to fetch banmen_all_full.png.`);
        console.error(`[ERROR] Status: ${e.response?.status}`);
        console.error(`[ERROR] Message: ${e.message}`);
        console.error(`[ERROR] Response Data:`, e.response?.data ? JSON.stringify(e.response.data).substring(0, 200) : 'None');
      }

      // サマリーの抽出 (「1. 対局の流れ・総評」から約400文字)
      let summary = "";
      if (responseText) {
        const match = responseText.match(/1\.\s*対局の流れ・総評([\s\S]*?)(?:2\.\s*私の敗因|$)/);
        if (match && match[1]) {
          summary = match[1].trim().substring(0, 400);
          if (match[1].trim().length > 400) summary += "...";
        } else {
          summary = responseText.substring(0, 400) + "...";
        }
      }

      res.json({
        reUrl,
        banmenImageUrl,
        summary,
        responseText,
        rawKif
      });
    } catch (error: any) {
      const errorMsg = "Failed to fetch report details";
      console.error("=========================================");
      console.error(`[FATAL ERROR] in /api/github/report/${req.params.category}/${req.params.subCategory}/${req.params.battleId}`);
      console.error("Error Message:", error.message);
      writeErrorLog(`Error in /api/github/report/${req.params.category}/${req.params.subCategory}/${req.params.battleId}`, error);
      
      if (error.response) {
        console.error("Axios Response Status:", error.response.status);
        console.error("Axios Response Data:", error.response.data);
      }
      console.error("=========================================");
      res.status(500).json({ error: errorMsg, details: error.message });
    }
  });

  // --- Gemini API チャットエンドポイント ---
  app.post("/api/chat", async (req, res) => {
    try {
      const { message, rawKif, responseText } = req.body;

      const THINKING_MODELS = new Set(["gemini-3.1-pro-preview", "gemini-3.1-flash-preview"]);
      const geminiModelsStr = process.env.GEMINI_MODELS || "gemini-3.1-pro-preview,gemini-3.1-flash-preview,gemini-flash-latest,gemini-2.5-pro,gemini-2.5-flash";
      // const modelList = geminiModelsStr.split(",").map(m => m.trim()).filter(m => m);
      const modelList = [
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash"
      ];

      const apiKey = process.env.API_KEY01;

      if (!apiKey) {
        return res.status(500).json({ error: "Gemini API key (API_KEY01) is not configured" });
      }

      const warsId = process.env.WARS_ID || "";
      const systemInstruction = `あなたは将棋のプロ棋士であり、私（${warsId}）の専属コーチです。
以下の【対局の棋譜】と、すでにあなたが分析した【事前の解析レポート】を読み込んでください。
ユーザーは、この対局についてさらに深く理解するためにあなたに質問をします。
プロの視点から、具体的かつ分かりやすく、ユーザーが強くなるためのアドバイスや変化手順を回答してください。

【対局の棋譜】
${rawKif || "棋譜データなし"}

【事前の解析レポート】
${responseText || "レポートデータなし"}`;

      let lastError: any = null;
      for (let modelIdx = 0; modelIdx < modelList.length; modelIdx++) {
        const model = modelList[modelIdx];
        const useThinking = THINKING_MODELS.has(model);

        try {
          const ai = new GoogleGenAI({ apiKey });
          const response = await ai.models.generateContent({
            model,
            contents: message,
            config: {
              systemInstruction,
              ...(useThinking ? { thinkingConfig: { thinkingLevel: ThinkingLevel.HIGH } } : {})
            }
          });

          let text = response.text || "";
          let thoughts = "";

          const thinkMatch = text.match(/<think>([\s\S]*?)<\/think>/);
          if (thinkMatch) {
            thoughts = thinkMatch[1].trim();
            text = text.replace(/<think>[\s\S]*?<\/think>/, "").trim();
          }

          return res.json({ text, thoughts });
        } catch (error: any) {
          lastError = error;
          console.warn(`${model} 失敗:`, error.message);
        }

        // 全キー失敗 → 次のモデルへ
        console.warn(`モデル ${model} 全キー失敗。次のモデルへ移行します`);
        if (modelIdx < modelList.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 10000));
        }
      }

      res.status(500).json({ error: "Gemini APIの呼び出しに失敗しました。全モデル・全キーで失敗しました。" });
    } catch (error: any) {
      console.error("Gemini API Error:", error);
      writeErrorLog("Error in /api/chat", error);
      res.status(500).json({ error: "Gemini APIの呼び出しに失敗しました。" });
    }
  });

  // API routes FIRST
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok" });
  });

  // Vite middleware for development or static files for production
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    // Production: serve static files from dist
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
