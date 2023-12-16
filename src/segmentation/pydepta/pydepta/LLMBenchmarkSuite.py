import openai
from transformers import AutoTokenizer
from petals import AutoDistributedModelForCausalLM
from typing import List, Dict
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)

# Choose any model available at https://health.petals.dev
model_name = "petals-team/StableBeluga2"  # This one is fine-tuned Llama 2 (70B)
#model_name = "bigscience/bloom-560m"  

#Connect to a distributed network hosting model layers
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoDistributedModelForCausalLM.from_pretrained(model_name)

def localLLM(prompt, max_new_tokens_amount=250, max_length=4096):
    inputs = tokenizer(f"{prompt}", return_tensors="pt", max_length=max_length, truncation=True)["input_ids"]
    outputs = model.generate(inputs, max_new_tokens=max_new_tokens_amount)
    response = tokenizer.decode(outputs[0])
    cleaned_response = response.replace("</s>", "")
    return cleaned_response  

config_file_path = '/home/jzale2/forward_data_llm_ie/config.json'

with open(config_file_path, "r") as config_file:
    config = json.load(config_file)
    openai.api_key = config["api_key"]


def chatGpt(prompt):
   # Use the GPT-3 model to generate a response
    chat_completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        #model="gpt-4-1106-preview",
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract the message generated by the chat model
    return chat_completion['choices'][0]['message']['content']

async def chatGpt_async(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: chatGpt(prompt))

async def localLLM_async(prompt: str, max_new_tokens_amount=250, max_length=4096) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: localLLM(prompt, max_new_tokens_amount, max_length))

async def compare_models_async(prompt: str) -> Dict[str, str]:
    gpt_response_task = asyncio.create_task(chatGpt_async(prompt))
    beluga_response_task = asyncio.create_task(localLLM_async(prompt))

    gpt_response, beluga_response = await asyncio.gather(gpt_response_task, beluga_response_task)

    return {
        'GPT3.5': gpt_response,
        'BELUGA': beluga_response
    }


def format_response(prompt: str, responses: Dict[str, str]) -> str:
    display_text = f"Prompt: {prompt}\n\n"
    display_text += "\n".join(f"{model} Response:\n{response}\n" 
                              for model, response in responses.items())
    display_text += "\n" + "-"*50 + "\n"
    return display_text

def process_prompt(prompt: str) -> str:
    responses = compare_models(prompt)
    return format_response(prompt, responses)

def read_prompts_from_file(file_path: str, delimiter: str = "#@@@@#") -> List[str]:
    with open(file_path, "r") as file:
        file_content = file.read()
        prompts = file_content.split(delimiter)
    return [prompt.strip() for prompt in prompts if prompt.strip()]

async def collect_all_responses_async(prompts: List[str]) -> str:
    response_tasks = [compare_models_async(prompt) for prompt in prompts]
    responses = await asyncio.gather(*response_tasks)
    return "\n".join(format_response(prompt, response) for prompt, response in zip(prompts, responses))

def write_to_file(file_path: str, data: str) -> None:
    with open(file_path, "a") as file:
        file.write(data)

async def main_async() -> None:
    prompts_file_path = "llm_benchmark_suite/text_analysis/prompt_analysis.txt"
    output_file_path = "llm_benchmark_suite/text_analysis/output_analysis.txt"

    prompts = read_prompts_from_file(prompts_file_path)
    all_responses = await collect_all_responses_async(prompts)
    write_to_file(output_file_path, all_responses)

if __name__ == "__main__":
    asyncio.run(main_async())