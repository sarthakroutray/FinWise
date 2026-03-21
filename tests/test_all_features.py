import asyncio
import json
import uuid
import httpx

async def run_chat(client: httpx.AsyncClient, payload: dict, expected_events: list):
    url = "http://localhost:8000/chat"
    print(f"\n▶ Testing: {payload['message']}")
    
    events_received = set()
    
    try:
        async with client.stream("POST", url, json=payload, timeout=90.0) as response:
            if response.status_code != 200:
                print(f"❌ HTTP Error {response.status_code}")
                msg = await response.aread()
                print(msg.decode())
                return False

            event_type = None
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                    events_received.add(event_type)
                elif line.startswith("data:"):
                    data_str = line.split(":", 1)[1].strip()
                    if event_type == "tool_call":
                        try:
                            data = json.loads(data_str)
                            print(f"  🟢 [Tool Called] {data.get('name')} | Args: {data.get('arguments')}")
                        except: pass
                    elif event_type == "tool_result":
                        print(f"  🟢 [Tool Result Returned]")
                    elif event_type == "chart":
                        print("  📊 [Chart Rendered]")
                    elif event_type == "token":
                        print(f"  📝 [Token]: {data_str.strip()}")
                    elif event_type == "agent_pitch":
                        try:
                            data = json.loads(data_str)
                            agent = data.get("agent")
                            txt = data.get("text", "")
                            if txt:
                                print(f"  🗣️  [{agent} Pitching] {txt.strip()}")
                        except: pass
                    elif event_type == "verdict":
                        try:
                            data = json.loads(data_str)
                            txt = data.get("text", "")
                            if txt:
                                print(f"  ⚖️  [Arbiter Verdict] {txt.strip()}")
                        except: pass
                    elif event_type == "agent_confidence":
                        try:
                            data = json.loads(data_str)
                            print(f"  🎯 [Agent Confidence] {data.get('agent')}: {data.get('score')}%")
                        except: pass
                    elif event_type == "error":
                        try:
                            data = json.loads(data_str)
                            print(f"  ❌ [ERROR] SERVER ERROR EVENT: {data.get('message')}")
                        except: pass
                    elif event_type == "debug":
                        try:
                            data = json.loads(data_str)
                            routing = next((s for s in data.get("stages", []) if s.get("name") == "routing"), None)
                            if routing:
                                print(f"  🚦 [Router Mode] {routing.get('mode')} (Score: {routing.get('score', 'N/A')})")
                            rag = next((s for s in data.get("stages", []) if s.get("name") == "rag_retrieval"), None)
                            if rag:
                                print(f"  📚 [RAG Chunks] {rag.get('chunks')} chunks retrieved")
                        except: pass
                    
                    if event_type == "done":
                        print("  🏁 [Stream Completed]")
                        break
    except Exception as e:
        print(f"❌ Exception during stream: {e}")
        return False

    missing = [e for e in expected_events if e not in events_received]
    if missing:
        print(f"❌ Failed: Missing expected events: {missing}")
        print(f"Received events: {events_received}")
        return False
    else:
        print(f"✅ Passed: Received all expected events {expected_events}.")
        return True

async def main():
    session_id = str(uuid.uuid4())
    print(f"Starting comprehensive feature tests (Session ID: {session_id})\n")
    
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(limits=limits) as client:
        
        # 1. Normal Chat + RAG Check
        success = await run_chat(
            client,
            {"message": "What were my most recent transactions?", "session_id": session_id},
            ["debug", "done"]
        )

        # 2. Math Tool Verification
        print("\nWaiting 20 seconds to respect API rate limits...")
        await asyncio.sleep(20)
        success &= await run_chat(
            client,
            {"message": "Calculate compound interest for $5000 at 7% for 20 years", "session_id": session_id},
            ["tool_call", "tool_result", "chart", "done"]
        )

        # 3. Scratchpad Query Verification
        print("\nWaiting 20 seconds to respect API rate limits...")
        await asyncio.sleep(20)
        success &= await run_chat(
            client,
            {"message": "Write a SQL query to find my largest expense category in the scratchpad.", "session_id": session_id},
            ["tool_call", "tool_result", "done"]
        )

        # 4. Multi-Agent Debate Verification (Thresholds, Parallel Agents, Confidence)
        print("\nWaiting 20 seconds to respect API rate limits...")
        await asyncio.sleep(20)
        success &= await run_chat(
            client,
            {"message": "I have $50,000 in cash. I am debating whether to aggressively invest it in the stock market or buy a safe CD to save it. What should I do?", "session_id": session_id},
            ["debate_start", "agent_pitch", "agent_confidence", "verdict", "debate_end", "done"]
        )

    if success:
        print("\n🎉 ALL TESTS PASSED.")
    else:
        print("\n💥 SOME TESTS FAILED.")
        import sys
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
