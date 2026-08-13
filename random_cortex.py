import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

html_code = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Header & Random Tag Converter</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: monospace; background-color: #1e1e1e; color: #d4d4d4; height: 100vh; display: flex; flex-direction: column; }
        header { background-color: #252526; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #3c3c3c; }
        header h1 { font-size: 16px; color: #61afef; }
        .controls { display: flex; gap: 12px; align-items: center; }
        .input-group { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #abb2bf; }
        .input-group input { background: #3c3c3c; border: 1px solid #555; color: #fff; padding: 4px 8px; border-radius: 4px; font-size: 12px; outline: none; }
        button { background-color: #0e639c; color: white; border: none; padding: 6px 14px; font-size: 13px; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #1177bb; }
        .copy-btn { background-color: #388e3c; }
        .container { display: flex; flex: 1; height: calc(100vh - 50px); }
        .editor-box { flex: 1; display: flex; flex-direction: column; border-right: 1px solid #3c3c3c; }
        .editor-header { background-color: #2d2d2d; padding: 6px 12px; font-size: 12px; color: #9cdcfe; font-weight: bold; border-bottom: 1px solid #3c3c3c; }
        textarea { flex: 1; background-color: #1e1e1e; color: #d4d4d4; border: none; outline: none; padding: 15px; font-family: "Courier New", Courier, monospace; font-size: 13px; resize: none; }
    </style>
</head>
<body>
    <header>
        <h1>⚡ Header & Tag Converter</h1>
        <div class="controls">
            <div class="input-group">
                <label>Recipient [to]:</label>
                <input type="text" id="recipientEmail" placeholder="email@gmail.com">
            </div>
            <div class="input-group">
                <label>Domain [placeholder5]:</label>
                <input type="text" id="mainDomain" placeholder="domain.com">
            </div>
            <button onclick="convertText()">Convert 🚀</button>
            <button class="copy-btn" onclick="copyOutput()">Copy 📋</button>
        </div>
    </header>
    <div class="container">
        <div class="editor-box">
            <div class="editor-header">Input</div>
            <textarea id="inputText" placeholder="Paste headers / HTML here..."></textarea>
        </div>
        <div class="editor-box">
            <div class="editor-header">Output</div>
            <textarea id="outputText" readonly placeholder="Converted output..."></textarea>
        </div>
    </div>
    <script>
        function detectPatternTag(token) {
            if (!token || !/^[a-zA-Z0-9]+$/.test(token)) return token;
            const len = token.length;
            const hasDigit = /\\d/.test(token);
            const hasLower = /[a-z]/.test(token);
            const hasUpper = /[A-Z]/.test(token);

            if (/^\\d+$/.test(token)) return `(n,${len})`;
            if (/^[a-z]+$/.test(token) && !hasDigit) return `(a,${len})`;
            if (/^[A-Z]+$/.test(token) && !hasDigit) return `(A,${len})`;
            if (/^[a-zA-Z]+$/.test(token) && hasLower && hasUpper) return `(Aa,${len})`;
            if (hasDigit && hasLower && !hasUpper) return `(an,${len})`;
            if (hasDigit && hasUpper && !hasLower) return `(An,${len})`;
            if (hasDigit && hasLower && hasUpper) return `(aAn,${len})`;
            return token;
        }

        function convertText() {
            let text = document.getElementById("inputText").value;
            const recipientEmail = document.getElementById("recipientEmail").value.trim();
            const mainDomain = document.getElementById("mainDomain").value.trim();
            if (!text) { document.getElementById("outputText").value = ""; return; }

            const smtpDateRegex = /(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\\s+\\d{1,2}\\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\\s+\\d{4}\\s+\\d{2}:\\d{2}:\\d{2}\\s+[\\+\\-]\\d{4}/gi;
            text = text.replace(smtpDateRegex, '[smtp_date]');

            if (recipientEmail) text = text.replaceAll(recipientEmail, '[to]');
            if (mainDomain) text = text.replaceAll(mainDomain, '[placeholder5]');

            text = text.replace(/\\b[a-zA-Z0-9]{5,}\\b/g, (match) => {
                if (/\\d/.test(match) || match.length >= 10 || match === match.toUpperCase()) {
                    return detectPatternTag(match);
                }
                return match;
            });
            document.getElementById("outputText").value = text;
        }
        document.getElementById("inputText").addEventListener("input", convertText);

        function copyOutput() {
            const output = document.getElementById("outputText");
            if (!output.value) return;
            output.select();
            document.execCommand("copy");
            alert("Copied!");
        }
    </script>
</body>
</html>
"""

components.html(html_code, height=800, scrolling=True)
