import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide", page_title="SMTP Extractor & Scan Matcher")

html_code = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SMTP Extract & Matcher</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
            background-color: #1e1e1e;
            color: #d4d4d4;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        header {
            background-color: #252526;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #3c3c3c;
        }
        header h1 { font-size: 16px; color: #61afef; font-weight: 600; }
        .stats { font-size: 13px; color: #9cdcfe; display: flex; gap: 20px; font-weight: bold; }
        .grid-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr 1fr;
            gap: 10px;
            padding: 10px;
            height: calc(100vh - 55px);
        }
        .box {
            display: flex;
            flex-direction: column;
            background-color: #252526;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            overflow: hidden;
        }
        .box-header {
            background-color: #2d2d2d;
            padding: 8px 12px;
            font-size: 12px;
            font-weight: bold;
            color: #abb2bf;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #3c3c3c;
            text-transform: uppercase;
        }
        .box-header span.tag {
            background: #3e4451;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            color: #d19a66;
        }
        textarea {
            flex: 1;
            background-color: #1e1e1e;
            color: #d4d4d4;
            border: none;
            outline: none;
            padding: 12px;
            font-family: "Courier New", Courier, monospace;
            font-size: 12px;
            line-height: 1.4;
            resize: none;
            white-space: pre;
            overflow-x: auto;
        }
        textarea::placeholder { color: #5c6370; }
        button.copy-btn {
            background-color: #28a745;
            color: white;
            border: none;
            padding: 3px 8px;
            font-size: 11px;
            border-radius: 3px;
            cursor: pointer;
            font-weight: bold;
        }
        button.copy-btn:hover { background-color: #218838; }
    </style>
</head>
<body>

    <header>
        <h1>⚡ SMTP Extractor & Scan Matcher</h1>
        <div class="stats">
            <span id="statExtracted">Extracted: 0</span>
            <span id="statMatched">Matched: 0</span>
        </div>
    </header>

    <div class="grid-container">
        <!-- Box 1: All_smtps -->
        <div class="box">
            <div class="box-header">
                <span>1. All_smtps (Paste Raw SMTPs)</span>
                <span class="tag">INPUT</span>
            </div>
            <textarea id="allSmtps" placeholder="Paste All_smtps list here..."></textarea>
        </div>

        <!-- Box 2: extract_email -->
        <div class="box">
            <div class="box-header">
                <span>2. extract_email (Extracted Emails)</span>
                <button class="copy-btn" onclick="copyBox('extractEmail')">Copy 📋</button>
            </div>
            <textarea id="extractEmail" readonly placeholder="Extracted emails will appear here automatically..."></textarea>
        </div>

        <!-- Box 3: Good_scan -->
        <div class="box">
            <div class="box-header">
                <span>3. Good_scan (Paste Scanned Emails/List)</span>
                <span class="tag">INPUT</span>
            </div>
            <textarea id="goodScan" placeholder="Paste Good_scan emails here..."></textarea>
        </div>

        <!-- Box 4: Test_all -->
        <div class="box">
            <div class="box-header">
                <span>4. Test_all (Matched Full SMTPs)</span>
                <button class="copy-btn" onclick="copyBox('testAll')">Copy 📋</button>
            </div>
            <textarea id="testAll" readonly placeholder="Matched SMTP lines will appear here automatically..."></textarea>
        </div>
    </div>

    <script>
        const allSmtpsInput = document.getElementById("allSmtps");
        const goodScanInput = document.getElementById("goodScan");
        const extractEmailOutput = document.getElementById("extractEmail");
        const testAllOutput = document.getElementById("testAll");

        function processAll() {
            const smtpsText = allSmtpsInput.value;
            const goodScanText = goodScanInput.value;

            // Strict & Robust Email Regex
            const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/gi;

            let smtpMap = new Map();
            let extractedSet = new Set();

            // 1. Process All_smtps
            if (smtpsText && smtpsText.trim()) {
                const lines = smtpsText.split(/\r?\n/);
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i].trim();
                    if (!line) continue;

                    const matches = line.match(emailRegex);
                    if (matches) {
                        for (let j = 0; j < matches.length; j++) {
                            const email = matches[j].toLowerCase();
                            extractedSet.add(email);
                            if (!smtpMap.has(email)) {
                                smtpMap.set(email, line);
                            }
                        }
                    }
                }
            }

            const extractedEmails = Array.from(extractedSet);
            extractEmailOutput.value = extractedEmails.join('\n');
            document.getElementById("statExtracted").innerText = "Extracted: " + extractedEmails.length;

            // 2. Process Good_scan & Match
            let matchedLines = [];
            let matchedSet = new Set();

            if (goodScanText && goodScanText.trim() && smtpMap.size > 0) {
                const scanLines = goodScanText.split(/\r?\n/);
                for (let i = 0; i < scanLines.length; i++) {
                    const line = scanLines[i].trim();
                    if (!line) continue;

                    const matches = line.match(emailRegex);
                    if (matches) {
                        for (let j = 0; j < matches.length; j++) {
                            const scanEmail = matches[j].toLowerCase();
                            if (smtpMap.has(scanEmail)) {
                                const fullSmtpLine = smtpMap.get(scanEmail);
                                if (!matchedSet.has(fullSmtpLine)) {
                                    matchedSet.add(fullSmtpLine);
                                    matchedLines.push(fullSmtpLine);
                                }
                            }
                        }
                    }
                }
            }

            testAllOutput.value = matchedLines.join('\n');
            document.getElementById("statMatched").innerText = "Matched: " + matchedLines.length;
        }

        // Instant Execution Listeners (typing, paste, input)
        allSmtpsInput.addEventListener("input", processAll);
        goodScanInput.addEventListener("input", processAll);

        allSmtpsInput.addEventListener("paste", () => setTimeout(processAll, 50));
        goodScanInput.addEventListener("paste", () => setTimeout(processAll, 50));

        function copyBox(id) {
            const textarea = document.getElementById(id);
            if (!textarea.value) return;
            textarea.select();
            document.execCommand("copy");
            alert("Copied!");
        }
    </script>
</body>
</html>
"""

components.html(html_code, height=900, scrolling=True)
