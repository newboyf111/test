---
name: model-selector
description: Helps users select the model with the shortest queue time for each request, ensuring faster response times.
---

# Model Selector Skill

This skill helps users select the model with the shortest queue time for each request, ensuring faster response times.

## When to Use This Skill

Use this skill when the user:

- Wants to optimize response times by using the least busy model
- Needs to automatically select the best available model for each request
- Asks about model availability or queue times
- Expresses concern about response speed

## How It Works

The Model Selector Skill:

1. Tracks queue times for multiple models including GPT-4, GPT-3.5-turbo, Claude-3 Opus, Claude-3 Sonnet, and Gemini Pro
2. Automatically updates queue times at regular intervals
3. Selects the model with the shortest queue time for each request
4. Provides status information for all models

## Usage Examples

### Example 1: Selecting the Fastest Model

```python
from src import ModelSelectorSkill

# Initialize the model selector
selector = ModelSelectorSkill()

# Get the model with the shortest queue time
result = selector.select_model()
print(f"Selected model: {result['selected_model']}")
print(f"Queue time: {result['queue_time']} seconds")
```

### Example 2: Checking All Model Statuses

```python
from src import ModelSelectorSkill

# Initialize the model selector
selector = ModelSelectorSkill()

# Get status of all models
status = selector.get_model_status()
for model, queue_time in status.items():
    print(f"{model}: {queue_time} seconds")
```

## Key Features

- **Automatic Model Selection**: Always chooses the model with the shortest queue time
- **Real-time Updates**: Automatically updates queue times every 60 seconds
- **Status Monitoring**: Provides current queue times for all models
- **Simple Integration**: Easy to integrate into existing projects

## Benefits

- **Faster Response Times**: By always using the least busy model
- **Improved User Experience**: Reduces waiting time for responses
- **Resource Optimization**: Efficiently distributes requests across available models
- **Transparency**: Provides visibility into model availability and queue times

## Integration

To use this skill in your project:

1. Import the ModelSelectorSkill class
2. Create an instance of the class
3. Call select_model() to get the best model for each request
4. Use the selected model for your API calls

This skill is designed to be lightweight and easy to integrate into any project that uses multiple AI models.