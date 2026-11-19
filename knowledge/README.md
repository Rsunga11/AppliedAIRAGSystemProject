# Maintaining the care knowledge base

Each Markdown section beginning with `## ` becomes a retrieval chunk. Put metadata immediately after the heading, before the explanatory text:

```markdown
## Example care topic
species: dog
topic: play
source_url: https://example.org/relevant-care-guidance
reviewed_on: YYYY-MM-DD

Write concise guidance supported by the linked source.
```

For every new or revised factual section:

- Use a reputable veterinary or animal-welfare source that directly supports the guidance, and include its URL.
- Set `reviewed_on` to the date the source and section were last checked, in ISO `YYYY-MM-DD` form.
- Keep any `recommended_minutes` or `recommended_per_day` values clearly framed as scheduling estimates unless the cited source explicitly supports them.
- Do not add medication dosages, diagnoses, or treatment instructions. Refer health concerns to a veterinarian.
- Add or update retrieval tests when introducing a section, especially when it provides task-review or routine-planning metadata.

The knowledge base is intentionally limited to dogs, cats, and rabbits. Rabbit entries use `species: other`, as configured by the advisor.
