
import glob
import json
import os
from typing import Any
from pydantic import BaseModel, TypeAdapter

from agent.asyncio import retry
from agent.oai_streaming import call_llm_with_streaming
from agent.utils import process_json_response
from jinja2 import Environment, FileSystemLoader
import logging

logger = logging.getLogger(__name__)


SLIDE_TEMPLATES = {
    "cover_slide": """A cover slide that introduces the presentation.
- Center the main title prominently.
- Add an optional subtitle in smaller font beneath the title.
- Include optional metadata (author, organization, date) at the bottom.
- Background may be solid color, gradient, or subtle imagery (avoid clutter).
    """,

    "text_content": """A slide focused on textual information.
- Use a clear heading at the top.
- Organize supporting text into short paragraphs or bullet points.
- Keep text concise; avoid long blocks.
- Ensure good spacing and readability.
    """,

    "image_content": """A slide focused on a single image or visual.
- Display the image as the main element, centered or full-bleed.
- Include a short caption or title (optional).
- Avoid large blocks of text; the image should be the focus.
    """,

    "tabular_content": """A slide that presents information in table form.
- Title at the top describing the table.
- Table should be clean, aligned, and easy to read.
- Use headers for columns/rows.
- Keep table size manageable; avoid cramming too much.
    """,

    "text_with_image": """A mixed-content slide with both text and image.
- Place heading at the top.
- Split layout into two sections: text on one side, image on the other.
- Keep balance between text and visual.
- Use bullets or short paragraphs for clarity.
    """,

    "comparison": """A slide for comparing two or more items.
- Title at the top.
- Use a two-column (or multi-column) layout for side-by-side comparison.
- Each column has its own subheading, bullet points, or visuals.
- Highlight key differences or similarities clearly.
    """,
}


class SlideOutline(BaseModel):
    template: str
    title: str
    content_outline: str

class SlideData(BaseModel):
    path: str
    title: str

PresentationOutline = TypeAdapter(list[SlideOutline])

SlideDataList = TypeAdapter(list[SlideData])


PRESENTATION_OUTLINE_PROMPT_TEMPLATE = """
You are a presentation outline generator. Your task is to generate an outline for a HTML presentation that strictly follow the slides plan. Use extra context from gathered information to help you with the outline generation.

The presentation outline should contain the following information for each slide:
- template: the slide template to use. Must be one of the following: {slide_templates}
- title: the title of the slide.
- content_outline: the content outline of the slide.

Return the presentation outline as a list of JSON objects as follows:
[
    {{"template": "slide 1 template", "title": "slide 1 title", "content_outline": "slide 1 content outline"}},
    {{"template": "slide 2 template", "title": "slide 2 title", "content_outline": "slide 2 content outline"}},
    ...
]

Presentation title: {presentation_title}

User request: {user_request}

Here is the gathered information:
{gathered_information}

Here is the slides plan:
{slides_plan}

Now, return only the required JSON with no additional text or formatting.
"""


HTML_SLIDE_GENERATION_PROMPT_TEMPLATE = """
You are the **HTML Slides Developer**, a frontend developer experienced at making turn the plan into static slides. You are part of a bigger system to build a polished, multi-page, responsive HTML representation from the prepared content.
                            
Your task is to build static stunning slides. Use **HTML5, Tailwind CSS** (no extra frameworks or build tools). Structure the slide according to the given layout template and content outline. Use extra context from gathered information to help you with the slide generation.

Before generating the slides, think about:
- The design of the slide
- The key content elements (text, images, tables, etc.) to include in the slide.

Response the HTML code of the slide wrapped in a code block like this:

```html
<your code here>
```

Slide title: {title}

Gathered information:
{gathered_information}

Layout template:
{layout_template}

Content outline:
{content_outline}

Now, generate and response the slide HTML code.
"""


async def create_slide(
    template: str,
    title: str,
    content_outline: str,
    gathered_information: str,
):
    if template not in SLIDE_TEMPLATES:
        raise ValueError(f"Invalid template: {template}")

    prompt = HTML_SLIDE_GENERATION_PROMPT_TEMPLATE.format(
        title=title,
        gathered_information=gathered_information,
        layout_template=SLIDE_TEMPLATES[template],
        content_outline=content_outline,
    )
    
    response = await call_llm_with_streaming(
        messages=[{"role": "user", "content": prompt}],
    )

    logger.info(f"Slide HTML: {response}")

    l = response.find("```html")
    r = response.find("```", start=l+7)
    response = response[l+7:r]
    response = response.strip("\n\t ")

    return response, prompt


async def get_slide_outline(
    slide_templates: dict[str, Any],
    gathered_information: str,
    slides_plan: str,
    presentation_title: str,
    user_request: str,
) -> PresentationOutline:
    template_list = ", ".join([f"'{key}'" for key in slide_templates.keys()])

    prompt = PRESENTATION_OUTLINE_PROMPT_TEMPLATE.format(
        slide_templates=template_list,
        gathered_information=gathered_information,
        slides_plan=slides_plan,
        presentation_title=presentation_title,
        user_request=user_request,
    )

    response = await call_llm_with_streaming(
        messages=[{"role": "user", "content": prompt}],
    )

    return PresentationOutline.validate_json(process_json_response(response))


async def make_slides(
    presentation_title: str,
    user_request: str,
    workdir: str,
):
    plan_paths = glob.glob(os.path.join(workdir, "**/slides_plan.md"), recursive=True)
    if len(plan_paths) == 0:
        raise Exception("Slides plan not found")
    with open(plan_paths[0], "r") as f:
        slides_plan = f.read()

    information_paths = glob.glob(os.path.join(workdir, "**/gathered_information.md"), recursive=True)
    if len(information_paths) == 0:
        raise Exception("Gathered information not found")
    with open(information_paths[0], "r") as f:
        gathered_information = f.read()
    
    presentation_outline: PresentationOutline = await retry(get_slide_outline)(
        SLIDE_TEMPLATES,
        gathered_information,
        slides_plan,
        presentation_title,
        user_request,
    )

    logger.info(f"Presentation outline: {PresentationOutline.dump_json(presentation_outline, indent=2)}")

    slide_data: SlideDataList = []

    for idx, slide_outline in enumerate(presentation_outline):
        logger.info(f"Creating slide {idx+1} of {len(presentation_outline)}: {slide_outline.title}")
        slide_html, prompt = await create_slide(
            slide_outline.template,
            slide_outline.title,
            slide_outline.content_outline,
            gathered_information,
        )
        slide_path = os.path.join(workdir, f"Slide_{idx}.html")
        prompt_path = os.path.join(workdir, f"Slide_{idx}.prompt.md")

        slide_data.append(SlideData(path=f"./Slide_{idx}.html", title=slide_outline.title))
        with open(slide_path, "w") as f:
            f.write(slide_html)
        with open(prompt_path, "w") as f:
            f.write(prompt)

    presentation_template = Environment(loader=FileSystemLoader('templates')).get_template("presentation_template.j2")
    presentation_html = presentation_template.render(
        presentation_title=presentation_title,
        slide_data=SlideDataList.dump_json(slide_data).decode("utf-8")
    )

    with open(os.path.join(workdir, "index.html"), "w") as f:
        f.write(presentation_html)
