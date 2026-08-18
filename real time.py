def fetch_sponsor_data(sponsor, s_date, e_date):
    endpoint = sponsor["endpoint"].strip()
    api_key = sponsor["api_key"].strip()
    
    # التعامل مع Everflow API
    if "everflow" in endpoint.lower():
        headers = {
            "x-eflow-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        # Structure الخاصة بـ Everflow Reporting
        payload = {
            "from": s_date.strftime("%Y-%m-%d"),
            "to": e_date.strftime("%Y-%m-%d"),
            "timezone_id": 80,  # UTC / Server Timezone
            "currency_id": "USD",
            "query": {
                "day_breakdown": False,
                "filters": []
            }
        }
        
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                res_json = response.json()
                table_data = res_json.get("table", [])
                parsed_items = []
                
                for row in table_data:
                    columns = row.get("columns", [])
                    reporting = row.get("reporting", {})
                    
                    # جلب قيمة Sub1 مباشرة من Columns
                    sub1_val = "N/A"
                    if columns:
                        sub1_val = str(columns[0].get("label", "N/A")).strip()
                    
                    parsed_items.append({
                        "sub1": sub1_val,
                        "clicks": reporting.get("clicks", 0),
                        "conversions": reporting.get("conversions", 0),
                        "revenue": float(reporting.get("payout", reporting.get("revenue", 0.0)))
                    })
                return parsed_items
            else:
                st.error(f"Everflow API Error: Status {response.status_code}")
                return None
        except Exception as e:
            st.error(f"Connection Error: {str(e)}")
            return None

    # للمنصات الأخرى
    else:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        params = {
            "start_date": str(s_date),
            "end_date": str(e_date),
            "group_by": "sub1"
        }
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None
