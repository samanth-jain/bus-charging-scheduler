# Bus Charging Scheduling

This repository contains an event-driven simulator and user interface designed to model, analyze, and optimize charging schedules for an electric bus fleet. The codebase leverages a Discrete Event Simulation (DES) paradigm to handle complex temporal interactions and resource constraints.

---

## How to Run Locally

### Prerequisites
* Python 3.9 or higher
* `pip` (Python package manager)

### Installation Steps

1. **Clone the Repository**
   Clone this repository to your local system and navigate to the directory:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install Dependencies**
   Install the required libraries listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

3. **Generate Scenario Data**
   Run the scenario generator script to populate the `data/` folder with JSON files corresponding to the five default test scenarios:
   ```bash
   python generate_scenarios.py
   ```

4. **Launch the Streamlit App**
   Start the Streamlit web application:
   ```bash
   streamlit run app.py
   ```
   Once started, the application will be accessible in your web browser at `http://localhost:8501`.

---

## How to Change a Weight

The optimization process balances multiple competing priorities using configurable weights. These parameters are read directly from the scenario configuration files, ensuring the scheduling engine remains decoupled from specific tuning values.

To adjust the weight values:

1. **Via the Scenario Files:**
   Open any scenario JSON file located inside the `data/` directory (e.g., `data/scenario_1.json`). Locate the `"weights"` object and change the values:
   ```json
   "weights": {
     "individual_wait": 1.5,
     "operator_grouping": 0.5,
     "overall_time": 1.0
   }
   ```
2. **Dynamic Overrides (UI-level):**
   The Streamlit sidebar exposes slider controls for each weight. These sliders load the default values from the selected scenario and reset to the scenario's JSON defaults whenever you choose a different scenario from the dropdown.
   <img width="387" height="491" alt="image" src="https://github.com/user-attachments/assets/89b69f47-4e0c-47cd-bb0f-94fd0f7a8aae" />


---

## How to Add a New Rule

The codebase supports adding both **soft rules** (used to prioritize queue order when resources are constrained) and **hard rules** (physical or regulatory constraints that cannot be violated).

### 1. Adding a Soft Rule (Queue Prioritization)
Soft rules are implemented as terms in the multi-criteria scoring function inside the `_score_bus` method. To add a new soft rule (e.g., prioritizing buses with lower state-of-charge):

1. Add a new weight parameter to your scenario configuration under `"weights"`, such as `"battery_priority"`.
2. Update the `_score_bus` method inside `scheduler.py` to calculate the new metric and add it to the return score.

### 2. Adding a Hard Rule (Routing or Safety Constraints)
Hard rules dictate how buses navigate the network and when they are allowed or forced to charge. These are evaluated inside the arrival handler `_handle_arrive`. 
To add a hard rule (e.g., forbidding charging if station queues are too long, or routing to alternative stations):

1. Modify `_handle_arrive` inside `scheduler.py` to evaluate the state of the bus and station against the new constraint.
2. Direct the bus to either enqueue at the station or bypass it based on the evaluated outcome.

*(Specific code implementation patterns for these modifications are detailed in the `ARCHITECTURE.md` file below).*

---
