import simpy
import random
import statistics
import numpy as np

# Assume the call center can service 24/7
# Assume there is one customer calling to the center every one minute
# => system can service 1440 customers per day

# Assume every customer takes 0.5 minute for serviced in CRS
# Assume every customer takes 5 minute for serviced in CSD
# Assume every customer takes 7 minute for serviced in PGD
# Assume every customer takes 5 minute for serviced in TSD
# Assume every customer takes 2 minute for serviced in AI/Robotics
TOTAL_CUSTOMERS = 1440*10
TOTAL_CUSTOMERS = 30000
# Simulation parameters
parameters = {
    'CRS': {'mu': 0.5, 'servers': 10},
    'AI/Robotics': {'mu': 2, 'servers': 5},
    'TSD': {'mu': 5, 'servers': 5},
    'PGT': {'mu': 7, 'servers': 5},
    'CSD': {'mu': 5, 'servers': 15}
}

# Updated transition probabilities to include the "Completed Support" state
transition_probabilities = {
    'CRS': [('TSD', 0.1), ('AI/Robotics', 0.3), ('PGT', 0.1), ('CSD', 0.5)],
    'TSD': [('CSD', 0.2), ('Completed Support', 0.8)],
    'PGT': [('CSD', 0.2), ('Completed Support', 0.8)],
    'AI/Robotics': [('CSD', 0.3), ('TSD', 0.1), ('PGT', 0.1), ('Completed Support', 0.5)],
    'CSD': [ ('PGT', 0.1), ('TSD', 0.1), ('Completed Support', 0.8)]
}

# Statistics class
class NodeStats:
    def __init__(self):
        self.waiting_times = []
        self.service_times = []
        self.queue_lengths = []
        self.utilization = []
        self.abandonment_count = 0  # New attribute to track abandonment count

    def customer_abandoned(self):
        self.abandonment_count += 1
        
    def add_stats(self, wait, service, count, servers):
        self.waiting_times.append(wait)
        self.service_times.append(service)
        self.queue_lengths.append(len(count.queue))
        self.utilization.append(count.count / servers)

    def compute_metrics(self):
        total_customers = len(self.waiting_times) + self.abandonment_count
        return {
            'average_waiting_time': statistics.mean(self.waiting_times) if self.waiting_times else 0,
            'average_service_time': statistics.mean(self.service_times) if self.service_times else 0,
            'average_queue_length': statistics.mean(self.queue_lengths) if self.queue_lengths else 0,
            'average_utilization': statistics.mean(self.utilization) if self.utilization else 0,
            'abandonment_rate': (self.abandonment_count / total_customers) if total_customers else 0
        }
        
# General Statistics
class GeneStats:
    def __init__(self):
        # First Call Resolution
        self.first_call_resolution_count = 0
        
        # Transfer Rates
        self.transfer_count = 0
        
    def compute(self):
        transfer_rates = 100 * self.transfer_count / TOTAL_CUSTOMERS
        return {
            'first_call_resoluton': 100 * self.first_call_resolution_count / TOTAL_CUSTOMERS,
            'transfer_rates': transfer_rates,
            'routing_efficiency': 100 - transfer_rates
        }

# Customer process
def customer(env, name, pathway, parameters):
    for node in pathway:
        arrival_time = env.now

        with nodes[node].request() as request:
            result = yield request | env.timeout(0.5)  # Adjust the timeout as needed
            if request not in result:  # Customer abandoned
                node_stats[node].customer_abandoned()
                wait = env.now - arrival_time
                node_stats[node].add_stats(wait, 0, nodes[node], parameters[node]['servers'])
                return

            wait = env.now - arrival_time
            service_time = random.expovariate(1.0 / parameters[node]['mu'])
            yield env.timeout(service_time)

            node_stats[node].add_stats(wait, service_time, nodes[node], parameters[node]['servers'])

# Weighted random choice using numpy
def weighted_random_choice(choices):
    choices, probabilities = zip(*choices)
    return np.random.choice(choices, p=probabilities)

def customer_pathway(env, customer_id, gene_stats):
    pathway = ['CRS']   # All customers start at the Call Routing System (CRS)
    current_node = 'CRS'
    while current_node != 'Completed Support':
        next_nodes = transition_probabilities[current_node]
        next_node = weighted_random_choice(next_nodes)
        if next_node == 'Completed Support':
            break
        pathway.append(next_node)
        current_node = next_node
    if len(pathway) == 2:
        gene_stats.first_call_resolution_count += 1
    else: 
        gene_stats.transfer_count += len(pathway) - 2
    yield env.process(customer(env, customer_id, pathway, parameters))

# After the simulation, evaluate the workload
def evaluate_workload(node_stats, gene_stats):
    total_customers_processed = sum(len(stats.waiting_times) for stats in node_stats.values())
    total_time_spent = sum(sum(stats.service_times + stats.waiting_times) for stats in node_stats.values())
    stats = gene_stats.compute()
    print(f"Total customers processed: {total_customers_processed}")
    print(f"Total time spent in system: {total_time_spent:.2f} minutes")
    print(f"First Call Resoluton: {stats['first_call_resoluton']:.2f} %")
    print(f"Transfer Rates: {stats['transfer_rates']:.2f} %")
    print(f"Routing Efficiency: {stats['routing_efficiency']:.2f} %")

# Environment setup
env = simpy.Environment()
nodes = {node: simpy.Resource(env, capacity=parameters[node]['servers']) for node in parameters}
node_stats = {node: NodeStats() for node in parameters}
gene_stats = GeneStats()

# Arrival process
def customer_arrivals(env, arrival_rate, gene_stats):
    for i in range(TOTAL_CUSTOMERS):
        customer_id = f'Customer_{i}'
        env.process(customer_pathway(env, customer_id, gene_stats))
        inter_arrival_time = random.expovariate(arrival_rate)
        yield env.timeout(inter_arrival_time)

# Setup the arrival process for the simulation
arrival_rate = 10
env.process(customer_arrivals(env, arrival_rate, gene_stats))

# Run the simulation
SIM_TIME = 24 * 60  # Simulate for 24 hours
# env.run(until=SIM_TIME)
env.run()

# Performance metrics calculation and printing
def print_performance_metrics(node_stats):
    for node, stats in node_stats.items():
        metrics = stats.compute_metrics()
        print(f"Node: {node}")
        print(f"  Average Waiting Time: {metrics['average_waiting_time']:.2f} minutes")
        print(f"  Average Service Time: {metrics['average_service_time']:.2f} minutes")
        print(f"  Average Queue Length: {metrics['average_queue_length']:.2f} customers")
        print(f"  Average Utilization: {metrics['average_utilization']*100:.2f}%")
        print(f"  Abandonment Rate: {metrics['abandonment_rate']*100:.2f}%")
        print("-" * 40)

print_performance_metrics(node_stats)
evaluate_workload(node_stats, gene_stats)