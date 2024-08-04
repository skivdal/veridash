from openai import OpenAI
from veridash_backend.commons.settings import Settings


class Translator:
    def __init__(self):
        s = Settings()

        self.client = OpenAI(
            organization=s.OPENAI_ORG,
            project=s.OPENAI_PROJECT,
            api_key=s.OPENAI_API_KEY,
        )


    def translate_sentences(self, sentences: list[str]) -> list[str]:
        s = '\n'.join(sentences)

        completion = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Please translate each newline-separated sentence to English, returning a similarly newline-separated output."},
                {"role": "user", "content": s},
            ],
        )

        content = completion.choices[0].message.content
        return [] if not content else content.split('\n')

