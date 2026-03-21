import asyncio
import json
import uuid
import httpx

async def main():
    session_id = str(uuid.uuid4())
    url = "http://localhost:8000/chat"
    
    # We will trigger a debate by asking a clear financial dilemma
    payload = {
        "message": "I have $10,000 saved up. Should I invest it in an index fund or put it in a high-yield savings account?",
        "session_id": session_id
    }
    
    print(f"Starting test debate stream for session {session_id}...")
    
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, timeout=60.0) as response:
            if response.status_code != 200:
                print(f"Error {response.status_code}")
                content = await response.aread()
                print(content.decode())
                return

            event_type = None
            
            # Tracking parallel tokens
            saver_tokens = []
            investor_tokens = []
            confidences = {}
            
            async for line in response.aiter_lines():
                if not line:
                    continue
                    
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_str = line.split(":", 1)[1].strip()
                    try:
                        data = json.loads(data_str)
                    except:
                        data = data_str
                        
                    if event_type == "agent_pitch":
                        agent = data.get("agent")
                        text = data.get("text")
                        if text:
                            if agent == "PennyWise":
                                saver_tokens.append(text)
                            elif agent == "BullRun":
                                investor_tokens.append(text)
                                
                    elif event_type == "agent_confidence":
                        agent = data.get("agent")
                        score = data.get("score")
                        confidences[agent] = score
                        print(f"✅ Received Confidence for {agent}: {score}%")
                        
                    elif event_type == "debug":
                        # Verify the router mode
                        stages = data.get("stages", [])
                        routing_stage = next((s for s in stages if s.get("name") == "routing"), None)
                        if routing_stage:
                            print(f"✅ Router assigned mode: {routing_stage.get('mode')}")
                            
            print("\n--- Test Results ---")
            print(f"Saver received {len(saver_tokens)} discrete tokens.")
            print(f"Investor received {len(investor_tokens)} discrete tokens.")
            print(f"Confidences received: {confidences}")
            
            # Since they are parallel, both arrays should be > 0 and interleaved in the stream,
            # but we just verify they both streamed tokens.
            if len(saver_tokens) > 0 and len(investor_tokens) > 0:
                print("✅ Parallel streaming assertion passed: Both agents returned tokens in the same connection stream.")
            else:
                print("❌ Streaming assertion failed.")

if __name__ == "__main__":
    asyncio.run(main())
