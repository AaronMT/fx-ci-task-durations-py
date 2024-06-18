import json
import pprint

# Load the JSON data
with open("taskgraph.json", "r") as file:
    data = json.load(file)

# Define the specific task to extract hierarchy
specific_task = "test-apk-fenix-debug"


# Function to extract dependencies for the specific task up to a certain depth
def extract_hierarchy(task_id, task_dict, depth, current_level=0):
    if (
        current_level < depth
        and task_id in task_dict
        and "dependencies" in task_dict[task_id]
    ):
        dependencies = task_dict[task_id]["dependencies"]
        return {
            task_id: {
                dep: extract_hierarchy(dep, task_dict, depth, current_level + 1)
                for dep in dependencies.values()
            }
        }
    return {}


# Set the depth limit
depth_limit = 3

# Create a hierarchy tree for the specific task up to the specified depth
hierarchy_tree = extract_hierarchy(specific_task, data, depth_limit)

# Write the updated data back to the JSON file
with open("taskgraph-processed.json", "w") as file:
    json.dump(hierarchy_tree, file, indent=4)
