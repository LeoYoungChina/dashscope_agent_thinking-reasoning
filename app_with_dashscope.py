import os
from textwrap import dedent
import streamlit as st
import json
from datetime import datetime
from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.tools.thinking import ThinkingTools
from agno.tools.tavily import TavilyTools
from agno.tools.reasoning import ReasoningTools
import time

def load_parts_info():
    try:
        with open("./fixing_parts.json", "r") as f:
            return json.load(f)
    except:
        return {}

def initialize_app():
    st.title("🔧 联想故障诊断助手")
    with st.sidebar:
        st.header("设置")
        think_mode = st.checkbox("启用思考模式", value=True)
        if think_mode:
            st.info("思考模式已启用，AI将展示推理过程")
        else:
            st.warning("思考模式已关闭，AI将直接给出结果")
    
    if "msgs" not in st.session_state:
        st.session_state["msgs"] = []
        
    if "parts_info" not in st.session_state:
        st.session_state["parts_info"] = load_parts_info()
        
    return think_mode

def setup_agent(think_mode):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts_info = st.session_state.get("parts_info", {})
    valid_parts = list(parts_info.keys())
    
    agent = Agent(
        model=DashScope(
            id="qwen3-235b-a22b-thinking-2507",
            api_key="sk-a3a228f6afcc4e3d9a34a5c5a7270fb3",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
        markdown=True,
        tools=[
            ThinkingTools(think=True),
            ReasoningTools(),
            TavilyTools(api_key="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"),
        ],
        instructions=dedent(f"""
            You are a Lenovo device fault diagnosis expert, specializing in analyzing customer service conversations and providing technical support.

            Current Time: {current_time}
            Core Capabilities:
            1.Parse device model, warranty status, and problem description from customer service conversations
            2.Analyze customer issues and determine if it's a software or hardware problem
            3.Provide step-by-step troubleshooting solutions
            4.For hardware issues, recommend specific replacement parts from the parts list
            5.For software issues, ensure Fix On Phone is set to True and provide remote troubleshooting

            Parts List
            Replaceable parts (must strictly use the following names):
            {"、".join(valid_parts) if valid_parts else "No available parts"}

            Output Format (strict JSON)
            Example 1 (Hardware Issue):
            {{
                "Device Information": {{
                    "Model": "Ideapad S500",
                    "Warranty Status": "1 year remaining",
                    "Problem Description": "Charging port failure"
                }},
                "Troubleshooting": [
                    "1.xxxxx",
                    "2.xxxxx",
                    "3.xxxxx",
                    "4.xxxxx",
                    "5.xxxxx"
                ],
                "Repair Recommendation": {{
                    "Fix On Phone": False,
                    "Parts Required": True,
                    "Recommended Parts": [  // 示例值，需根据实际分析动态生成
                        "AC Adapter"  // 确保 name 在 valid_parts 中存在
                    ]
                }}
            }}
            
            Example 2 (Software Issue):
            {{
                "Device Information": {{
                    "Model": "ThinkPad X1 Carbon",
                    "Warranty Status": "Active",
                    "Problem Description": "System freezing after Windows update"
                }},
                "Troubleshooting": [
                    "1.Restart computer in Safe Mode",
                    "2.Uninstall recent Windows updates",
                    "3.Run System File Checker (SFC)",
                    "4.Update graphics drivers",
                    "5.Check for disk errors"
                ],
                "Repair Recommendation": {{
                    "Fix On Phone": True,
                    "Parts Required": False,
                    "Recommended Parts": []
                }}
            }}

            Important Rules:
            1. You must use the part names listed above
            2. Only return pure JSON format
            3. If no matching parts are found, return an empty array for parts

        """),
        show_tool_calls=True,
    )
    agent.think = think_mode
    return agent

def prepare_messages(think_mode):
    messages = []
    for i, msg in enumerate(st.session_state["msgs"]):
        content = msg["content"]
        if (i == len(st.session_state["msgs"]) - 1 and 
            msg["role"] == "user" and not think_mode):
            content = f"/no_think {content}"
        messages.append({"role": msg["role"], "content": content})
    return messages

def process_assistant_response(agent, messages, think_mode):
    # 创建两个占位符，一个用于思考过程，一个用于最终回答
    thinking_placeholder = st.empty()
    message_placeholder = st.empty()
    
    full_response = ""
    reasoning_content = ""
    is_thinking = False
    
    run_response = agent.run(
        messages=messages, 
        stream=True,
        extra_body={
            "enable_thinking": think_mode,
            "thinking_budget": 100
        }
    )
    
    for chunk in run_response:
        # 处理思考内容
        if hasattr(chunk, 'reasoning_content') and chunk.reasoning_content:
            if not is_thinking and think_mode:
                is_thinking = True
                thinking_placeholder.markdown("### Thinking")
            
            reasoning_content += chunk.reasoning_content
            if think_mode:
                thinking_placeholder.markdown("### Thinking\n" + reasoning_content + "▌")
        
        # 处理回答内容
        if chunk.content:
            # 如果是第一次收到内容，添加标题
            if not full_response and think_mode:
                message_placeholder.markdown("### 💡 Solution")
            
            full_response += chunk.content
            if think_mode:
                message_placeholder.markdown("### 💡 Solution\n" + full_response + "▌")
            else:
                message_placeholder.markdown(full_response + "▌")
    
    # 更新最终内容（去掉光标）
    if think_mode and reasoning_content:
        thinking_placeholder.markdown("### Thinking\n" + reasoning_content)
    
    if think_mode and full_response:
        message_placeholder.markdown("### 💡 Solution\n" + full_response)
    else:
        message_placeholder.markdown(full_response)
    
    return full_response

def main():
    think_mode = initialize_app()
    agent = setup_agent(think_mode)
    
    with st.sidebar:
        conversation_input = st.text_area("粘贴客服对话", height=300)
    
    if st.sidebar.button("🔍 分析对话") and conversation_input:
        prompt = f"请分析以下对话并提供建议:\n\n{conversation_input}"
        st.session_state["msgs"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            messages = prepare_messages(think_mode)
            full_response = process_assistant_response(agent, messages, think_mode)
            st.session_state["msgs"].append({"role": "assistant", "content": full_response})

    if prompt := st.chat_input("输入问题"):
        st.session_state["msgs"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            messages = prepare_messages(think_mode)
            full_response = process_assistant_response(agent, messages, think_mode)
            st.session_state["msgs"].append({"role": "assistant", "content": full_response})

if __name__ == "__main__":
    main()
