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
        const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/gi;
        let debounceTimer = null;

        function processAll() {
            const smtpsVal = document.getElementById("allSmtps").value;
            const scanVal = document.getElementById("goodScan").value;

            if (!smtpsVal || !smtpsVal.trim()) {
                document.getElementById("extractEmail").value = "";
                document.getElementById("testAll").value = "";
                document.getElementById("statExtracted").innerText = "Extracted: 0";
                document.getElementById("statMatched").innerText = "Matched: 0";
                return;
            }

            // 1. Instant Global Email Extraction for Box 2
            const rawExtracted = smtpsVal.match(emailRegex) || [];
            const uniqueEmails = [];
            const emailSet = new Set();

            for (let i = 0; i < rawExtracted.length; i++) {
                const lower = rawExtracted[i].toLowerCase();
                if (!emailSet.has(lower)) {
                    emailSet.add(lower);
                    uniqueEmails.push(lower);
                }
            }

            document.getElementById("extractEmail").value = uniqueEmails.join('\n');
            document.getElementById("statExtracted").innerText = "Extracted: " + uniqueEmails.length;

            // 2. Line Mapping for Full SMTP Matching (Box 4)
            const lines = smtpsVal.split(/\r?\n/);
            const smtpMap = new Map();

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                if (!line) continue;
                const lineEmails = line.match(emailRegex);
                if (lineEmails) {
                    for (let j = 0; j < lineEmails.length; j++) {
                        const em = lineEmails[j].toLowerCase();
                        if (!smtpMap.has(em)) {
                            smtpMap.set(em, line);
                        }
                    }
                }
            }

            // 3. Process Good_scan
            if (scanVal && scanVal.trim()) {
                const scanMatches = scanVal.match(emailRegex) || [];
                const matchedLines = [];
                const matchedSet = new Set();

                for (let i = 0; i < scanMatches.length; i++) {
                    const scanEmail = scanMatches[i].toLowerCase();
                    if (smtpMap.has(scanEmail)) {
                        const fullLine = smtpMap.get(scanEmail);
                        if (!matchedSet.has(fullLine)) {
                            matchedSet.add(fullLine);
                            matchedLines.push(fullLine);
                        }
                    }
                }

                document.getElementById("testAll").value = matchedLines.join('\n');
                document.getElementById("statMatched").innerText = "Matched: " + matchedLines.length;
            } else {
                document.getElementById("testAll").value = "";
                document.getElementById("statMatched").innerText = "Matched: 0";
            }
        }

        function triggerDebouncedProcess() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(processAll, 200);
        }

        // Event listeners for smooth paste & typing
        document.getElementById("allSmtps").addEventListener("input", triggerDebouncedProcess);
        document.getElementById("goodScan").addEventListener("input", triggerDebouncedProcess);

        function copyBox(id) {
            const textarea = document.getElementById(id);
            if (!textarea || !textarea.value) return;
            textarea.select();
            document.execCommand("copy");
            alert("Copied!");
        }
    </script>
</body>
</html>
"""

components.html(html_code, height=900, scrolling=True)
