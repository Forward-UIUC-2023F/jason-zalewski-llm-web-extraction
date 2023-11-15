import ast
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import openai
import json
from typing import List, Any
import re
from pathlib import Path


config_file_path = '/Users/jasonz/forward_data_lab_llmie/forward_data-llm_ie/config.json'

with open(config_file_path, "r") as config_file:
    config = json.load(config_file)
    openai.api_key = config["api_key"]

def chatGpt(prompt):
   # Use the GPT-3 model to generate a response
    chat_completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract the message generated by the chat model
    return chat_completion['choices'][0]['message']['content']


class ProfessorExtractor:
    def __init__(self):
        self.raw_html = ""
        self.raw_text = ""
        self.prof_names_set = set()

    def fetch_html_from_url(self, url):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            def handle_response(response):
                if response.url == url and response.status == 200:
                    self.raw_html = response.text()

            page.on("response", handle_response)
            page.goto(url)
            browser.close()
        
        return self.raw_html

    def extract_text(self):
        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(self.raw_html, 'html.parser')
        # Extract raw text from the parsed HTML
        self.raw_text = soup.get_text(separator=' ', strip=True)
        return self.raw_text


# Do one region at a time, can try to make this faster later by finding names in more than one region
    def find_names_in_region(self, region: List[List[Any]]):
        
        def classify_region_for_prof_names(region: List[List[Any]]) -> bool:
            print(f"region: {region}")
            prompt = f"If This Given List has atleast one Professor Name inside of it, output exactly yes or no- {region}"
            print(f"prompt: {prompt}")
            answer: str = chatGpt(prompt)
            print(f"answer: {answer}")
            return True if answer.strip().lower() == "yes" else False

        if classify_region_for_prof_names(region) is True:
            print("Succesfull Classify")
            counter = 0
            combined_record = []
            for record in region:
                combined_record.append(record)
                counter += 1
                if counter % 3 == 0 or record == region[-1]:
                    
                    # To Improve accuracy of less than 3 records duplicate 1 record
                    if record == region[-1]:
                       combined_record.append(record) 

                    # Flatten the list of lists into a single list of strings
                    flat_list = [item for sublist in combined_record for item in sublist if item is not None]
                    # Now join the strings
                    combined_records_str = " ".join(flat_list)

                    # prompt = (
                    #     f"Extract only the full names of individuals without any titles, positions, or additional information. "
                    #     f"The term 'professor' should not be included with the names. "
                    #     f"List each unique name as a comma-separated list, formatted for direct inclusion in a Python set. "
                    #     f"If no names that match these criteria are found, output 'null'.\n\n"
                    #     f"Text: {combined_records_str}"
                    # )
                    prompt = (
                        "Extract only the full names of individuals, ensuring that each name is presented in 'First Name Last Name' order "
                        "without any titles, positions, or additional information. "
                        "The term 'professor' should not be included with the names. "
                        "List each unique name as a comma-separated list, formatted for direct inclusion in a Python set. "
                        "If no names that match these criteria are found, output 'null'.\n\n"
                        f"Text: {combined_records_str}"
                    )       
                    answer: str = chatGpt(prompt)
                    print(f"answer: {answer}")
                    if "null" in answer.lower(): continue 
                    else:
                        # Split the string into a list using the comma as a delimiter
                        names_list = answer.split(', ')

                        def format_names(names_list):
                            formatted_names = []
                            for name in names_list:
                                # Remove any quotation marks
                                name = name.replace('"', '')
                                name = name.replace("'", '')
                                # Check if the name is some variant of "null"
                                if "null" in name.lower():
                                    continue  # Skip adding to the list
                                formatted_names.append(name)
                            return formatted_names
                        
                        formated_names_list = format_names(names_list)
                        self.prof_names_set.update(formated_names_list)

                    combined_record = []
                
        else: print("Failed Classify")
        print(f"Professor Name Set: {self.prof_names_set}")
    


    def extract_prof_names_to_json(self):
        
        def extract_text_around_name(name, text,  window=8):
            # Find the position of the name in the text
            start_index = text.find(name)
            if start_index == -1:
                return None  # Name not found in the text

            # Find the indices of the words around the name
            words_before = text[:start_index].split()
            words_after = text[start_index:].split()

            # Calculate the start and end indices for the window of text around the name
            start_word_index = max(0, len(words_before) - window)
            end_word_index = min(len(words_after), window + 1)

            # Extract the text around the name
            before_text = ' '.join(words_before[start_word_index:])
            after_text = ' '.join(words_after[:end_word_index])

            # Combine the text before and after the name
            return before_text + ' ' + after_text
           


        def find_names_in_html():
            # Parse the HTML to extract text
            soup = BeautifulSoup(self.raw_html, 'html.parser')
            html_text = soup.get_text(separator=' ')
            # Search for each name in the HTML text
            for name in self.prof_names_set:
                if name in html_text:
                    # Find the same name in the raw text and extract context around it
                    context = extract_text_around_name(name, html_text)
                    if context:
                        prompt = (
                        f"Output in JSON FORMAT- The following page contains a list of faculty information, find the professor's name, position, and research interests of the professor{name} "
                        "And nobody else! "
                        "If no names that match these criteria are found, output 'null'.\n\n"
                        f"Text: {context}"
                    )       
                        answer: str = chatGpt(prompt)
                        print(f"answer: {answer}")
                        if answer.strip().lower() == "null" : continue 
                        else:
                            # TODO Need to add a check if Valid JSON before inserting into file
                            def append_to_json_file(file_path, data_string):
                                # Attempt to parse the JSON string
                                try:
                                    data = json.loads(data_string)
                                except json.JSONDecodeError as e:
                                    # If an error occurs, print the error and the invalid JSON string
                                    print("Invalid JSON:", e)
                                    print(f"Received invalid data: {data_string}")
                                    return  # Exit the function without appending

                                # Check if the file exists
                                if Path(file_path).exists():
                                    # Read the existing content
                                    with open(file_path, 'r+', encoding='utf-8') as file:
                                        # Go to the beginning of the file and load the data
                                        file.seek(0)
                                        try:
                                            file_data = json.load(file)
                                            if isinstance(file_data, list):  # Check if the file contains a list
                                                # Append the new data and write back to the file
                                                file_data.append(data)
                                                file.seek(0)  # Go back to the start of the file
                                                json.dump(file_data, file, indent=4)
                                                file.truncate()  # Remove any remaining parts of old data
                                        except json.JSONDecodeError:
                                            print("File is not valid JSON, or list is not at the root. Appending not possible.")
                                else:
                                    # Create a new file with the data in a list
                                    with open(file_path, 'w', encoding='utf-8') as file:
                                        json.dump([data], file, indent=4)

                            # Convert the string to a dictionary
                            #data_object = json.loads(answer)

                            # Now you can append it to the JSON file
                            json_file_path = 'illlini3_professors.json'  # Change this to the actual path you want to use
                            append_to_json_file(json_file_path, answer)
                    else:
                        print("Can't find the name in text")


        find_names_in_html()
    
    # Example of another method that could use the fetched HTML or raw text
    def process_html(self):
        # Do something with self.raw_html or self.raw_text
        pass