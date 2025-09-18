import base64
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from openai import OpenAI
from dotenv import load_dotenv
from PIL import Image, ImageTk
import requests
from io import BytesIO

load_dotenv()
client = OpenAI()

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def get_image_description(base64_image):
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in a concise but detailed manner, note the style of the image like is it photorealistic or a painting, suitable as a prompt for an image generation model like DALL-E, keep it short and simple."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        messagebox.showerror("API Error", f"Failed to get description: {e}")
        return None

def generate_image_from_text(prompt):
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url
    except Exception as e:
        messagebox.showerror("DALL-E API Error", f"Failed to generate image: {e}")
        return None

class ImageToImageApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image-to-Text-to-Image Generator")
        self.root.geometry("1200x700")

        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.select_button = tk.Button(main_frame, text="Select Image to Start", command=self.process_image)
        self.select_button.pack(pady=10)

        content_frame = tk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_columnconfigure(2, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        placeholder_img = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
        self.placeholder = ImageTk.PhotoImage(placeholder_img)

        self.image_label = tk.Label(content_frame, image=self.placeholder, text="Original image will appear here", compound='center')
        self.image_label.grid(row=0, column=0, padx=10, sticky="nsew")

        self.description_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, height=10, width=40)
        self.description_text.grid(row=0, column=1, padx=10, sticky="nsew")
        self.description_text.insert(tk.END, "AI-generated description will appear here...")
        self.description_text.config(state=tk.DISABLED)
        
        self.generated_image_label = tk.Label(content_frame, image=self.placeholder, text="Newly generated image will appear here", compound='center')
        self.generated_image_label.grid(row=0, column=2, padx=10, sticky="nsew")

    def process_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.gif *.bmp")]
        )
        if not file_path:
            return

        try:
            img = Image.open(file_path)
            img.thumbnail((400, 400))
            photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not load image: {e}")
            return

        self.generated_image_label.config(image=self.placeholder, text="Newly generated image will appear here")
        self.description_text.config(state=tk.NORMAL)
        self.description_text.delete('1.0', tk.END)
        self.description_text.insert(tk.END, "Generating description, please wait...")
        self.root.update_idletasks()

        base64_image = encode_image_to_base64(file_path)
        description = get_image_description(base64_image)

        self.description_text.delete('1.0', tk.END)
        if not description:
            self.description_text.insert(tk.END, "Failed to generate a description.")
            self.description_text.config(state=tk.DISABLED)
            return
        
        self.description_text.insert(tk.END, description)

        self.description_text.insert(tk.END, "\n\n-------------------\nNow, generating a new image...")
        self.root.update_idletasks()

        image_url = generate_image_from_text(description)

        if image_url:
            try:
                response = requests.get(image_url)
                img_data = BytesIO(response.content)
                new_img = Image.open(img_data)
                new_img.thumbnail((400, 400))
                new_photo = ImageTk.PhotoImage(new_img)

                self.generated_image_label.config(image=new_photo, text="")
                self.generated_image_label.image = new_photo
                self.description_text.insert(tk.END, "\nImage generation complete!")
            except Exception as e:
                messagebox.showerror("Download Error", f"Failed to display generated image: {e}")
                self.description_text.insert(tk.END, "\nError displaying new image.")
        else:
            self.description_text.insert(tk.END, "\nImage generation failed.")
            
        self.description_text.config(state=tk.DISABLED)

def main():
    root = tk.Tk()
    app = ImageToImageApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()