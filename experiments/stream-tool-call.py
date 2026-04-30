import litellm
import json

# 1. Define a simple tool schema
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather in a given location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "The city name"}
            },
            "required": ["location"]
        }
    }
}]

messages = [{"role": "user", "content": "What is the weather like in Paris?"}]

# 2. Initiate the streaming connection
print("Initiating stream...\n")
response = litellm.completion(
    model="anthropic/claude-3-haiku-20240307", # Or any tool-capable Anthropic model
    messages=messages,
    tools=tools,
    stream=True
)

# 3. State variables to hold the streaming fragments
tool_name = None
tool_id = None
args_buffer = ""

# 4. The Event Loop
for chunk in response:
    delta = chunk.choices[0].delta

    # A. Handle standard text (if the model speaks before using the tool)
    if delta.content:
        print(f"Text Delta: {delta.content}")

    # B. Handle tool call streams
    if delta.tool_calls:
        tool_call_chunk = delta.tool_calls[0]
        
        # Capture ID and Name on the very first tool chunk
        if tool_call_chunk.id:
            tool_id = tool_call_chunk.id
            tool_name = tool_call_chunk.function.name
            print(f"\n[Signal Received: Starting tool '{tool_name}' with ID '{tool_id}']")
        
        # Buffer the JSON fragments as they arrive
        if tool_call_chunk.function.arguments:
            fragment = tool_call_chunk.function.arguments
            args_buffer += fragment
            print(f"  + JSON Fragment: {fragment}")

# 5. The stream is closed. Execute!
print("\n[Stream Closed]")
if tool_name:
    print(f"\nAssembled JSON String: {args_buffer}")
    
    # Parse the complete string into a Python dictionary
    parsed_arguments = json.loads(args_buffer)
    print(f"Parsed Dictionary: {parsed_arguments}")
    
    # -> HERE is where your code would actually run: 
    # -> weather_data = get_weather(parsed_arguments["location"])