import pygame
import random
import math
import csv
import pandas as pd

# Participant number
participant_number = 63

# Treatment possibilities
treatment_scenarios = [('H1', 'H2', 'H3'), ('H1', 'H3', 'H2'), ('H2', 'H1', 'H3'), ('H2', 'H3', 'H1'), ('H3', 'H1', 'H2'), ('H3', 'H2', 'H1')]

# Pick a random treatment scenario
treatment = random.choice(treatment_scenarios)
# treatment = ('H2', 'H3', 'H1')

# Game variables/constants
width, height = 1500, 840
road_width = 3*width
pavement_height = 210
road_height = 420
# curb_height = 10
no_road_markings = 30
road_marking_width = 100
road_marking_height = 30
light_pole_height = 20
light_pole_width = 20
background_colour = 'silver'
instruction_background_colour = '#222233'
instruction_text_colour = '#AACCFF'
road_colour = (50, 50, 50)
player_colour = (255, 0, 0)
pedestrian_colour = (0, 0, 255)
road_marking_colour = (255, 255, 255)
player_radius = 17.5
player_velocity = [0,0]
FPS = 60
Timestep = 1/FPS
no_pedestrians = 40
x_closest_pedestrians = 20
num_lights = 24
player_x = 20
target_size = 30
no_targets = 3   
target_colour = (0, 255, 0)

# Pedestrian target variables
dash_length = 10
gap_length = 5

# Pedstrian target
target_bottom = height - pavement_height
H2_target_x = -100
H3_target_x = (2*width)-50

'''
Helbing's Social Force Model defines the following constants:

Target Force: F_t = m((v_0*e_i) - v)/T_alpha
    m - Mass of the pedestrian
    v_0 - Magnitude of the desired velocity of pedestrian i 
    e_i = Direction of the desired speed of pedestrian i
    v - current velocity of pedestrian i
    T_alpha - Relaxation time

Interaction force between pedestrians: F_s = A_s * e_ij * exp(-g_ij/B_s)
    where g_ij = d_ij - (r_i + r_j) 
    A_s - Social repulsive force between pedestrians
    e_ij - Normalised vector on the normal direction between pedestrians i and j
    B_s - Characteristic distance between pedestrians i and j
    d_ij - Distance between pedestrians i and j
    r_i - Radius of pedestrian i
    r_j - Radius of pedestrian j 

Interaction force between pedestrian and boundary: F_b = A_b * e_ib * exp(g_ib/B_b)
    where g_ib = d_ib - r_i
    A_b - Social repulsive force between pedestrian and boundary
    e_ib - Normalised vector on the normal direction between pedestrian i and boundary b
    B_b - Characteristic distance between pedestrian i and boundary b
    d_ib - Distance between pedestrian i and boundary b

Notes: 
    - Don't need to worry about attraction forces from other pedestrians
    - r_i = r_j = r (radius of pedestrian - assumed to be the same in my case)
    - F_total = F_t + sum(F_s) + sum(F_b)
    - for sum(F_s) only consider the x closest pedestrians and remember to skip the current pedestrian (ie cannot interact with itself)
    - ignore mass or just set m = 1

'''
# Pedestrian constants (Play around with these values)
# Target Force:
m = 1 # Mass of pedestrian
v_0 = 1.34 * 70 # Desired velocity
T_alpha = 0.5 # Relaxation time

# Interaction force between pedestrians:
A_s = 1000 # Social repulsive force between pedestrians
B_s = 50 # Characteristic distance between pedestrians
r = player_radius # Radius of pedestrian

# Interaction force between pedestrian and boundary:
A_b = 500 # Social repulsive force between pedestrian and boundary
B_b = 30 # Characteristic distance between pedestrian and boundary

pedestrian_constants = [m, v_0, T_alpha, A_s, B_s, r, A_b, B_b]

# Initialize pygame
pygame.init()
screen = pygame.display.set_mode((width, height))
pygame.display.set_caption('Virtual Experiment')
game_start = pygame.time.get_ticks()
clock = pygame.time.Clock()
running = True

# Player class
class Player:
    def __init__(self, x, y, radius):
        self.x = x
        self.y = y
        self.radius = radius

    def cal_social_force(self, pedestrian_coords, constants, closest_pedestrians = x_closest_pedestrians):
        # Unpack constants
        A_s = constants[3]
        B_s = constants[4]
        r = constants[5]

        F_s = [0,0] # initalise force vector as 0
        r_player = (self.x, self.y) # position of the pedestrian alpha

        # Sort the pedestrians by distance
        sorted_pedestrians = sorted(pedestrian_coords, key = lambda pedestrian: math.hypot(pedestrian[0] - r_player[0], pedestrian[1] - r_player[1]))

        # Calculate the social force but only for the closest pedestrians
        for pedestrian in sorted_pedestrians[:closest_pedestrians]:
            r_beta = (pedestrian[0], pedestrian[1]) 
            distance = math.hypot(r_player[0] - r_beta[0], r_player[1] - r_beta[1])
            if distance > B_s:
                continue
            else:
                e_ij = [(r_beta[0] - r_player[0]) / distance, 
                        (r_beta[1] - r_player[1]) / distance]
                # let the player experience a weaker social force so its easier to move through the crowd
                F_s[0] -= A_s * e_ij[0] * math.exp(-(distance - 2*r) / B_s) * 0.5  
                F_s[1] -= A_s * e_ij[1] * math.exp(-(distance - 2*r) / B_s) * 0.5
        return F_s

    def calculate_boundary_force(self, rectangle_corners, constants):
        # Unpack constants
        A_b = constants[6]
        B_b = constants[7]
        r = constants[5]

        F_b = [0, 0]

        if self.y >= height/2:
            x1, y1, x2, y2 = rectangle_corners[1]
            distance_to_boundary = abs(self.y - y2)
            closest_y = y2
        else:
            x1, y1, x2, y2 = rectangle_corners[0]
            distance_to_boundary = abs(self.y - y1)
            closest_y = y1
        
        closest_x = max(x1, min(self.x, x2))

        if distance_to_boundary == 0:
            distance_to_boundary = 1e-6 # Prevent division by zero

        if distance_to_boundary <= B_b:
            e_ib = [(closest_x - self.x) / distance_to_boundary, 
                    (closest_y - self.y) / distance_to_boundary]
            F_b[0] -= A_b * e_ib[0] * math.exp((distance_to_boundary - r) / B_b)
            F_b[1] -= A_b * e_ib[1] * math.exp((distance_to_boundary - r) / B_b)
        
        return F_b, x1, y1, x2, y2

    def move_towards(self, target_x, target_y, velocity_x, velocity_y, dt, pedestrian_coords, constants):
        # Unpack constants
        v_0 = constants[1]
        T_alpha = constants[2]

        # Initialize the new velocity
        new_velocity_x = velocity_x
        new_velocity_y = velocity_y

        distance = math.hypot(target_x - self.x, target_y - self.y)

        if distance > 1:
            # Calculate the direction vector (unit vector)
            direction_x = (target_x - self.x) / distance
            direction_y = (target_y - self.y) / distance

            # Calculate the target force
            distance_to_target = math.hypot(target_x - self.x, target_y - self.y)
            if distance_to_target > 0:  # Prevent division by zero
                e_i = [(target_x - self.x) / distance_to_target,
                    (target_y - self.y) / distance_to_target]
            else:
                e_i = [0, 0]  # No movement if already at the target
            F_t = [m * ((v_0 * e_i[0]) - velocity_x) / T_alpha, 
                m * ((v_0 * e_i[1]) - velocity_y) / T_alpha]

            # Calculate social force
            F_s = self.cal_social_force(pedestrian_coords, constants)

            # Calculate boundary force
            F_b, x1, y1, x2, y2 = self.calculate_boundary_force(rectangle_corners, constants)

            # Calculate the total force
            F_total = [F_t[0] + F_s[0] + F_b[0], F_t[1] + F_s[1] + F_b[1]]

            # Update the player
            new_velocity_x += (F_total[0] * Timestep)
            new_velocity_y += (F_total[1] * Timestep)

            new_x = self.x + new_velocity_x * Timestep
            new_y = self.y + new_velocity_y * Timestep

            # Check if the new position is past the boundary
            if new_y > height - player_radius:
                new_y = height - player_radius
                new_velocity_y = 0
            elif new_y < player_radius:
                new_y = player_radius
                new_velocity_y = 0

            move_distance = math.hypot(new_x - self.x, new_y - self.y)

            # If the distance to the target is less than the movement distance, move to the target
            if move_distance >= distance:
                self.x = target_x
                self.y = target_y
            else:
                self.x = new_x
                self.y = new_y

            velocity_mag = math.hypot(new_velocity_x, new_velocity_y)
            if new_velocity_x < -80:
                new_velocity_x = 0
            elif velocity_mag > v_0:
                new_velocity_x = (v_0 / velocity_mag) * new_velocity_x
                new_velocity_y = (v_0 / velocity_mag) * new_velocity_y

        return self.x, self.y, new_velocity_x, new_velocity_y

# Pedestrian class
class Pedestrian:
    def __init__(self, x, y, radius):
        self.x = x
        self.y = y
        self.radius = radius
    
    def cal_social_force(self, pedestrian_coords, constants, closest_pedestrians = x_closest_pedestrians):
        # Unpack constants
        A_s = constants[3]
        B_s = constants[4]
        r = constants[5]

        F_s = [0,0] # initalise force vector as 0
        r_alpha = (self.x, self.y) # position of the pedestrian alpha

        pedestrian_coords.append((player.x, player.y)) # add player to the list of pedestrians

        # Sort the pedestrians by distance
        sorted_pedestrians = sorted(pedestrian_coords, key = lambda pedestrian: math.hypot(pedestrian[0] - r_alpha[0], pedestrian[1] - r_alpha[1]))

        # Calculate the social force but only for the closest pedestrians
        for pedestrian in sorted_pedestrians[:closest_pedestrians]:
            if pedestrian == r_alpha:
                continue # skip the current pedestrian
            r_beta = (pedestrian[0], pedestrian[1]) 
            distance = math.hypot(r_alpha[0] - r_beta[0], r_alpha[1] - r_beta[1])
            if distance > B_s:
                continue
            else:
                e_ij = [(r_beta[0] - r_alpha[0]) / distance, 
                        (r_beta[1] - r_alpha[1]) / distance]
                F_s[0] -= A_s * e_ij[0] * math.exp(-(distance - 2*r) / B_s)
                F_s[1] -= A_s * e_ij[1] * math.exp(-(distance - 2*r) / B_s)
        
        pedestrian_coords.pop() # remove player from the list of pedestrians
        return F_s
    
    def calculate_boundary_force(self, rectangle_corners, constants):
        # Unpack constants
        A_b = constants[6]
        B_b = constants[7]
        r = constants[5]

        F_b = [0, 0]

        if self.y >= height/2:
            x1, y1, x2, y2 = rectangle_corners[1]
        else:
            x1, y1, x2, y2 = rectangle_corners[0]
        
        distance_to_top = abs(self.y - y1)
        distance_to_bottom = abs(self.y - y2)

        if distance_to_top < distance_to_bottom:
            closest_y = y1
            distance_to_boundary = distance_to_top
        else:
            closest_y = y2
            distance_to_boundary = distance_to_bottom
        
        closest_x = max(x1, min(self.x, x2))

        if distance_to_boundary == 0:
            distance_to_boundary = 1e-6 # Prevent division by zero

        if distance_to_boundary <= B_b:
            e_ib = [(closest_x - self.x) / distance_to_boundary, 
                    (closest_y - self.y) / distance_to_boundary]
            F_b[0] -= A_b * e_ib[0] * math.exp((distance_to_boundary - r) / B_b)
            F_b[1] -= A_b * e_ib[1] * math.exp((distance_to_boundary - r) / B_b)
        
        return F_b, x1, y1, x2, y2

    def move_towards(self, target_x, target_y, velocity_x, velocity_y, pedestrian_coords, constants):
        # Unpack constants
        m = constants[0]
        v_0 = constants[1]
        T_alpha = constants[2]

        # Initialize the new velocity
        new_velocity_x = velocity_x
        new_velocity_y = velocity_y

        # Calculate the social force
        F_s = self.cal_social_force(pedestrian_coords, constants)

        # Calculate the boundary force
        F_b, x1, y1, x2, y2 = self.calculate_boundary_force(rectangle_corners, constants)

        # Calculate the target force
        distance_to_target = math.hypot(target_x - self.x, target_y - self.y)
        if distance_to_target > 0:  # Prevent division by zero
            e_i = [(target_x - self.x) / distance_to_target,
                   (target_y - self.y) / distance_to_target]
        else:
            e_i = [0, 0]  # No movement if already at the target
        F_t = [m * ((v_0 * e_i[0]) - velocity_x) / T_alpha, 
               m * ((v_0 * e_i[1]) - velocity_y) / T_alpha]

        # Calculate the total force
        F_total = [F_t[0] + F_s[0] + F_b[0], F_t[1] + F_s[1] + F_b[1]]

        # print(f'Pedestrian force: {F_total}')

        # Update the pedestrian
        new_velocity_x += (F_total[0] * Timestep)
        new_velocity_y += (F_total[1] * Timestep)

        new_x = self.x + new_velocity_x * Timestep
        new_y = self.y + new_velocity_y * Timestep

        # Check if the new position is past the boundary
        if new_y < y1 + r:
            new_y = y1 + r
            new_velocity_y = 0
        elif new_y > y2 - r:
            new_y = y2 - r
            new_velocity_y = 0

        collision = False

        # Check if the new position is inside any other pedestrian
        pedestrian_coords.append((player.x, player.y)) # add the player to the list of pedestrians
        for pedestrian in pedestrian_coords:
            if pedestrian == (self.x, self.y):
                continue # skip the current pedestrian
            distance = math.hypot(new_x - pedestrian[0], new_y - pedestrian[1])
            if distance < 2*r:
                collision = True 
                normalised_velocity = [new_velocity_x / math.hypot(new_velocity_x, new_velocity_y),
                                       new_velocity_y / math.hypot(new_velocity_x, new_velocity_y)]
                new_x -= normalised_velocity[0] * distance
                new_y -= normalised_velocity[1] * distance
        pedestrian_coords.pop() # remove the player from the list of pedestrians

        # Check if the new position is inside the player
        # distance_to_player = math.hypot(new_x - player.x, new_y - player.y)
        # if distance_to_player <= 2*r:
        #     collision = True
        #     normalised_velocity = [new_velocity_x / math.hypot(new_velocity_x, new_velocity_y),
        #                            new_velocity_y / math.hypot(new_velocity_x, new_velocity_y)]
        #     new_x -= normalised_velocity[0] * distance_to_player
        #     new_y -= normalised_velocity[1] * distance_to_player

        if not collision:
            self.x = new_x
            self.y = new_y
        
        velocity_mag = math.hypot(new_velocity_x, new_velocity_y)
        if velocity_mag > v_0:
            new_velocity_x = (v_0 / velocity_mag) * new_velocity_x
            new_velocity_y = (v_0 / velocity_mag) * new_velocity_y
        
        return self.x, self.y, new_velocity_x, new_velocity_y


# Generate pedestrian coordinates
def generate_pedestrian_coords(no_pedestrians, width, height, player_x, player_y, treatment):
    pedestrian_coords = []
    min_distance = 2 * player_radius  

    for i in range(no_pedestrians):
        while True:  
            if treatment == 'H2':
                x = random.randint(width + (width/2), width*2)
                y = random.randint((height - pavement_height) + 2*player_radius, height - 2*player_radius)
            elif treatment == 'H3':
                x = random.randint(-300, width/2 - 300)
                y = random.randint((height - pavement_height) + 2*player_radius, height - 2*player_radius)

            # Check if the new pedestrian is too close to any existing pedestrian
            too_close = False
            for ped_x, ped_y in pedestrian_coords:
                distance = math.hypot(x - ped_x, y - ped_y)
                if distance < min_distance:
                    too_close = True
                    break  # No need to check further; regenerate
            
            # Check against the player's position
            if math.hypot(x - player_x, y - player_y) < min_distance:
                too_close = True
                continue

            if not too_close:  # If the position is valid, add it to the list
                pedestrian_coords.append((x, y))
                break  # Exit the while loop and move to the next pedestrian

    return pedestrian_coords

# Function to create the lights surface
def lights(glow_dim, glow_bright, treatment):
    # Create lists for the light surfaces and their centres
    light_surfaces = []
    light_centres = []
    split = int(num_lights/2)
    light_radius_bright = glow_bright
    light_radius_dim = glow_dim

    # Bright lights
    for i in range(split):
        layers = 70
        light_surf = pygame.Surface((light_radius_bright*2, light_radius_bright*2), pygame.SRCALPHA)
        for j in range(layers, 0, -1):
            distance = j * light_radius_bright/layers
            alpha = glow_bright/(math.pi * (distance) ** 2) * (90 * glow_bright)
            alpha = max(0, min(255, alpha))
            pygame.draw.circle(light_surf, (0, 0, 0, alpha), light_surf.get_rect().center, int(distance))
        light_surfaces.append(light_surf)
        x1 = (road_width/split) * (i - 2)
        x2 = (road_width/split) * (i - 1)
        x = (x1 + x2)/2
        if treatment == 'H2':
            light_centres.append((x - light_radius_bright, (height - pavement_height) - light_radius_bright))
        elif treatment == 'H3':
            light_centres.append((x - light_radius_bright, pavement_height - light_radius_bright))
    
    # Dim lights
    for i in range(split):
        layers = 50
        light_surf = pygame.Surface((light_radius_dim*2, light_radius_dim*2), pygame.SRCALPHA)
        for j in range(layers, 0, -1):
            distance = j * light_radius_dim/layers
            alpha = glow_dim/(math.pi * (distance) ** 2) * (30 * glow_dim)
            alpha = max(0, min(255, alpha))
            pygame.draw.circle(light_surf, (0, 0, 0, alpha), light_surf.get_rect().center, int(distance))
        light_surfaces.append(light_surf)
        x1 = (road_width/split) * (i - 2)
        x2 = (road_width/split) * (i - 1)
        x = (x1 + x2)/2
        if treatment == 'H2':
            light_centres.append((x - light_radius_dim, pavement_height - light_radius_dim))
        elif treatment == 'H3':
            light_centres.append((x - light_radius_dim, (height - pavement_height) - light_radius_dim))

    return light_surfaces, light_centres, light_radius_dim

# Function to display instructions
def display_instructions(screen, instructions_text):
    screen.fill(instruction_background_colour)
    for i, line in enumerate(instructions_text):
        text = instruction_font.render(line, True, instruction_text_colour)
        text_rect = text.get_rect(center=(width // 2, 50 + i * 30))
        screen.blit(text, text_rect)
    pygame.display.update()

# Function to save data
def save_data(H1_time, H2_time, H3_time, player_position_H1, player_position_H2, player_position_H3, cross_road_H1, 
            cross_road_H2, cross_road_H3, click_H1, click_H2, click_H3, click_position_H1, click_position_H2, 
            click_position_H3, pedestrian_positions_H2, pedestrian_positions_H3, treatment):
    # Prepare the data
    position_data_H1 = {'H1_Player_position': player_position_H1}
    position_data_H2 = {'H2_Player_position': player_position_H2}
    position_data_H3 = {'H3_Player_position': player_position_H3}
    pedestrian_positions_H2 = {'H2_Pedestrian_positions': pedestrian_positions_H2}
    pedestrian_positions_H3 = {'H3_Pedestrian_positions': pedestrian_positions_H3}
    extra_data = {'H1_time': [H1_time], 'H2_time': [H2_time], 'H3_time': [H3_time], 'Crossed_road_H1': [cross_road_H1], 
            'Crossed_road_H2': [cross_road_H2], 'Crossed_road_H3': [cross_road_H3], 'Clicks_H1': [click_H1], 'Clicks_H2': [click_H2], 
            'Clicks_H3': [click_H3], 'Treatment': [treatment]}
    click_position_data_H1 = {'Click_position_H1': click_position_H1} 
    click_position_data_H2 = {'Click_position_H2': click_position_H2}
    click_position_data_H3 = {'Click_position_H3': click_position_H3}
    
    # Create dataframes
    df_position_H1 = pd.DataFrame(position_data_H1)
    df_position_H2 = pd.DataFrame(position_data_H2)
    df_position_H3 = pd.DataFrame(position_data_H3)
    df_pedestrian_positions_H2 = pd.DataFrame(pedestrian_positions_H2)
    df_pedestrian_positions_H3 = pd.DataFrame(pedestrian_positions_H3)
    df_extra = pd.DataFrame(extra_data)
    df_click_position_H1 = pd.DataFrame(click_position_data_H1)
    df_click_position_H2 = pd.DataFrame(click_position_data_H2)
    df_click_position_H3 = pd.DataFrame(click_position_data_H3)

    # Save the data to CSV files with participant_number in the filename
    df_position_H1.to_csv(f'position_data_H1_{participant_number}.csv', index=False)
    df_position_H2.to_csv(f'position_data_H2_{participant_number}.csv', index=False)
    df_position_H3.to_csv(f'position_data_H3_{participant_number}.csv', index=False)
    df_pedestrian_positions_H2.to_csv(f'pedestrian_positions_H2_{participant_number}.csv', index=False)
    df_pedestrian_positions_H3.to_csv(f'pedestrian_positions_H3_{participant_number}.csv', index=False)
    df_extra.to_csv(f'extra_data_{participant_number}.csv', index=False)
    df_click_position_H1.to_csv(f'click_position_data_H1_{participant_number}.csv', index=False)
    df_click_position_H2.to_csv(f'click_position_data_H2_{participant_number}.csv', index=False)
    df_click_position_H3.to_csv(f'click_position_data_H3_{participant_number}.csv', index=False)


# Create dimmed overlay surface
dimness = 220
dim_surf = pygame.Surface((width, height), pygame.SRCALPHA)
dim_surf.fill((0, 0, 0, dimness))

# Create the road (x1, y1, width, height)
rectangles = [
    (-width/2, pavement_height, road_width, road_height)
]

# Create the road markings
road_markings = []
for i in range(no_road_markings):
    road_markings.append((((i - 5)*150), height/2 - road_marking_height/2, road_marking_width, road_marking_height))

# Create the targets
targets = []
for i in range(no_targets):
    if (i+1) % 2 == 0:
        targets.append(((i+1)*500, height - pavement_height, target_size, target_size))
    else:
        targets.append(((i+1)*500, pavement_height, target_size, target_size))

# Create the pavements
rectangle_corners = [((-width/2)-500, 0, (2*width)+(width/2)+200, pavement_height),
                     ((-width/2)-500, (height - pavement_height), (2*width)+(width/2)+200, height)]

# # Create the curbs
# curbs = [((-width/2)-500, pavement_height - curb_height, (2*width)+(width/2)+200, curb_height),
#          ((-width/2)-500, height - pavement_height, (2*width)+(width/2)+200, curb_height)]

instructions_text_1 = ['Thank you for taking part in this study!',
                       '',
                       'This experiment is conducted by researchers at the University of Bristol.',
                       'The objective of this experiment is to investigate factors affecting pedestrian route choices.',
                       'The experiment should only take 5-6 minutes to complete.',
                       'Your age, gender, the routes you decide to take, the paths of the pedestrians, and some extra data (clicks, roads crossed, time taken)',
                       'within the experiment will be recorded.',
                       'No personal data will be collected, and therefore your responses are completely anonymous.',
                       '',
                       'If you have any questions, contact: Arthur Yamaguchi (qv20601@bristol.ac.uk)',
                       'If you have any concerns about this experiment, contact: research-ethics@bristol.ac.uk',
                       '',
                       'By continuing with the experiment, you are consenting to the following:',
                       '1. You have read and understood the introduction to the experiment.',
                       '2. Your participation is voluntary, and you are free to stop the experiment at any point by closing the window (in this case no data will be collected).',
                       '3. Information collected will be analysed to help understand how pedestrian route choices are affected by light and crowds,', 
                       'in order to improve pedestrian friendly spaces.',
                       '4. You understand that after the study, anonymised data may be made available as “open data”. ',
                       'This means that data will be publicly available and may be used for purposes not related to this study.', 
                       'However, it will not be possible to identify you from this data.',
                       '5. You understand that you may withdraw your data, without giving a reason, until the point at which your data is anonymised.',
                       'After this point it will no longer be possible to identify your data.',
                       '',
                       'If you agree and would like to continue with the experiment, please press SPACE.',
                       'If you do not agree, please close the window.']

instructions_text_2 = ['Welcome to a simple route choice simulation!',
                        '',
                        'In this simulation, you are the red circle and you can move by clicking on the screen.',
                        'Your player will move towards the point you click on.',
                        '',
                        'The first simulation is for you to get used to the controls and the environment so feel free to take your time.',
                        'Your player is fixed to the centre of the screen and the camera will follow you as you move.',
                        'This means that the environment will move around you as you move.',
                        '',
                        'In this initial simulation, navigate to the green boxes on the screen.',
                        'A new box will appear after you reach the previous one.',
                        'The simulation will end after you reach the last box.',
                        'The white rectangles represent road markings. You can walk over them.',
                        '',
                        'Press SPACE to start!']

instructions_text_3 = ['Congratulations, you have completed the initial navigation!',
                       '',
                       'Hopefully you are now comfortable with the controls and the environment.',
                       '',
                       'You will now be presented with 3 scenarios.',
                       'In each scenario, your objective is to navigate to the end of a straight road.',
                       'The end point of the road is represented by a dashed red line, which is far off to the right hand side of the screen.',
                       'The lighting on each side of the road will differ and depending on the scenario, you will encounter other pedestrians.',
                       'The pedestrians will be represented by blue circles.',
                       '',
                       'As mentioned previously, this simulation aims to gather data on route choices,',
                       'so take whichever route you feel you would take if presented with the same scenario in real life.',
                       '',
                       'Press SPACE to start the first simulation!']

instructions_text_4 = ['Congratulations!',
                       '', 
                       'The next screen will be the second scenario.',
                       'Again, please take whichever route you feel is best.',
                       '',
                       'Press SPACE to start the second simualtion!',]

instructions_text_5 = ['Congratulations!',
                       '',
                       'The next screen will be the final scenario.',
                       'Again, please take whichever route you feel is best.',
                       '',
                       'Press SPACE to start the final simulation!']

final_screen_text = ['Thank you for participating in the study!',
                     '',
                     'If you have any further questions, please do not hesitate to ask by emailing qv20601@bristol.ac.uk.',
                     '',
                     'You may now close the window to exit the simulation.']

instruction_font = pygame.font.Font(None, 30)

# Create Player 
player = Player(player_x, height - (pavement_height/2), player_radius)
target_x, target_y = player.x, player.y
moving = False

# Display the instructions and decide which screen to show
display_instructions(screen, instructions_text_1)
instruction_1_active = True
instruction_2_active = False
initial_navigation = False
instruction_3_active = False
instruction_4_active = False
instruction_5_active = False
flags_treatment = {'H1': False, 'H2': False, 'H3': False}
final_screen = False
lights_on = True

# Generate pedestrian coordinates, thier velocities and create pedestrians
pedestrian_coords_H2 = generate_pedestrian_coords(no_pedestrians, width, height, player_x, height - (pavement_height/2), 'H2')
pedestrian_coords_H3 = generate_pedestrian_coords(no_pedestrians, width, height, player_x, pavement_height/2, 'H3')
pedestrian_velocities_H2 = [(0, 0) for i in range(no_pedestrians)]
pedestrian_velocities_H3 = [(0, 0) for i in range(no_pedestrians)]
pedestrians_H2 = [Pedestrian(pedestrian_coords_H2[i][0], pedestrian_coords_H2[i][1], player_radius) for i in range(no_pedestrians)]
pedestrians_H3 = [Pedestrian(pedestrian_coords_H3[i][0], pedestrian_coords_H3[i][1], player_radius) for i in range(no_pedestrians)]
pedestrian_target_H2 = [(H2_target_x, random.randint(int(target_bottom + player_radius), int(height - player_radius))) for i in range(no_pedestrians)]
pedestrian_target_H3 = [(H3_target_x, random.randint(int(target_bottom + player_radius), int(height - player_radius))) for i in range(no_pedestrians)]

pedestrian_coords_initial = []

# Camera offset
camera_offset_x = 0

# Generate the lights
light_surfaces_H2, light_centres_H2, light_radius_dim_H2 = lights(100, 200, 'H2')
light_surfaces_H3, light_centres_H3, light_radius_dim_H3 = lights(100, 200, 'H3')

# Generate the lights for H1
light_centres_H1 = [list(coords) for coords in light_centres_H2]
top_centre = light_centres_H1[0][1]
bottom_centre = light_centres_H1[12][1]
for i in range(int(num_lights/4)):
    top_right_index = int((num_lights/4) + i)
    bottom_right_index = int((3*num_lights/4) + i)
    light_centres_H1[top_right_index] = (light_centres_H1[top_right_index][0], bottom_centre - light_radius_dim_H2)
    light_centres_H1[bottom_right_index] = (light_centres_H1[bottom_right_index][0], top_centre + light_radius_dim_H2)

# # Create the light poles
# light_poles = []
# for i in range(num_lights):
#     if i < num_lights/2:
#         light_poles.append((light_centres_H2[i][0] - light_pole_width/2, 210 - light_pole_height/2, light_pole_width, light_pole_height))
#     else:
#         light_poles.append((light_centres_H2[i][0] - light_pole_width/2, height - 210 - light_pole_height/2, light_pole_width, light_pole_height))

# Start times
H1_start = None
H2_start = None
H3_start = None

# Data collection parameters
data_interval = 0.5
data_timer = 0
player_position_H1 = []
player_position_H2 = []
player_position_H3 = []
pedestrian_positions_H2 = []
pedestrian_positions_H3 = []
cross_road_H1 = 0
cross_road_H2 = 0
cross_road_H3 = 0
bottom = True
click_H1 = 0
click_H2 = 0
click_H3 = 0
click_position_H1 = []
click_position_H2 = []
click_position_H3 = []
current_target_index = 0

# Main loop
while running:

    clock.tick(FPS) # cap the frame rate to 60fps
    # Set the clock/delta time in seconds since the last frame, used for framerate independent physics
    dt = clock.tick(FPS) / 1000

    data_timer += dt

    # EVENTS
    for event in pygame.event.get():
        # Pygame.QUIT event means that the user has clicked the close button
        if event.type == pygame.QUIT:
            running = False
        
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and instruction_1_active:
            instruction_1_active = False
            instruction_2_active = True

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and instruction_2_active:
            instruction_2_active = False
            initial_navigation = True

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and instruction_3_active:
            instruction_3_active = False
            flags_treatment[treatment[0]] = True

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and instruction_4_active:
            instruction_4_active = False
            flags_treatment[treatment[1]] = True
        
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE and instruction_5_active:
            instruction_5_active = False
            flags_treatment[treatment[2]] = True

        # Move player using the mouse
        elif event.type == pygame.MOUSEBUTTONDOWN:
            target_x, target_y = pygame.mouse.get_pos()
            target_x += camera_offset_x
            moving = True
            # print(f'Player position: {player.x, player.y}')
            if flags_treatment['H1']:
                click_H1 += 1
                click_position_H1.append((target_x, target_y))
            elif flags_treatment['H2']:
                click_H2 += 1
                click_position_H2.append((target_x, target_y))
            elif flags_treatment['H3']:
                click_H3 += 1
                click_position_H3.append((target_x, target_y))

    if instruction_1_active:
        continue

    if instruction_2_active:
        display_instructions(screen, instructions_text_2)
        continue

    if initial_navigation:
        if moving:
            player_new_x, player_new_y, player_new_vel_x, player_new_vel_y = player.move_towards(
                target_x, target_y, player_velocity[0], player_velocity[1], dt, pedestrian_coords_initial, pedestrian_constants)
            player_velocity = [player_new_vel_x, player_new_vel_y]
            
            if math.hypot(target_x - player.x, target_y - player.y) < 1:
                moving = False

        # Check if the player has reached the target
        init_target_x = targets[current_target_index][0] + target_size/2
        init_target_y = targets[current_target_index][1] + target_size/2
        if math.hypot(init_target_x - player.x, init_target_y - player.y) < target_size/2:
            current_target_index += 1

        camera_offset_x = player.x - width/2

        # Draw the background
        screen.fill(road_colour)

        # Draw the road markings
        for rect in road_markings:
            pygame.draw.rect(screen, road_marking_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # Draw the current target
        if current_target_index < no_targets:
            pygame.draw.rect(screen, target_colour, (targets[current_target_index][0] - camera_offset_x, targets[current_target_index][1], 
                                                    targets[current_target_index][2], targets[current_target_index][3]))
        
        # Draw the player
        pygame.draw.circle(screen, player_colour, (int(width/2), int(player.y)), player_radius)

        pygame.display.update()

        # Check if the player has reached the final target
        if current_target_index > no_targets-1:
            initial_navigation = False
            instruction_3_active = True

            # Reset the player's position
            player.x, player.y = player_x, height - (pavement_height/2)
            # Reset the player's target
            target_x, target_y = player.x, player.y
            # Reset the player's velocity
            player_velocity = [0, 0]

    if instruction_3_active:
        display_instructions(screen, instructions_text_3)
        continue    

    if flags_treatment['H1']:
        if H1_start is None:
            H1_start = pygame.time.get_ticks()

        if moving:
            player_new_x, player_new_y, player_new_vel_x, player_new_vel_y = player.move_towards(
                target_x, target_y, player_velocity[0], player_velocity[1], dt, pedestrian_coords_initial, pedestrian_constants)
            player_velocity = [player_new_vel_x, player_new_vel_y]

            if math.hypot(target_x - player.x, target_y - player.y) < 1:
                moving = False
            
        if bottom:
            if player.y < pavement_height:
                cross_road_H1 += 1
                bottom = False

        elif not bottom:
            if player.y > height - pavement_height:
                cross_road_H1 += 1
                bottom = True

        if data_timer >= data_interval:
            player_position_H1.append((player.x, player.y))
            data_timer = 0

        camera_offset_x = player.x - width/2

        # Draw the background
        screen.fill(background_colour)

        # Draw the road
        for rect in rectangles:
            pygame.draw.rect(screen, road_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # Draw the road markings
        for rect in road_markings:
            pygame.draw.rect(screen, road_marking_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # # Draw the curb
        # for rect in curbs:
        #     pygame.draw.rect(screen, curb_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # # Draw the light poles
        # for rect in light_poles:
        #     pygame.draw.rect(screen, light_pole_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # Draw the player
        pygame.draw.circle(screen, player_colour, (int(width/2), int(player.y)), player_radius)

        if lights_on:
            # Reset the dimmed overlay
            dim_surf.fill((0, 0, 0, dimness))

            # Add the lights
            for light_surf, (x,y) in zip(light_surfaces_H2, light_centres_H1):
                adjusted_x = x - camera_offset_x
                dim_surf.blit(light_surf, (adjusted_x, y), special_flags=pygame.BLEND_RGBA_SUB)
            # Draw the dimmed overlay and lights onto the screen
            screen.blit(dim_surf, (0, 0))

        # Draw the dashed line (target)
        x_adjusted = (width*2)-50 - camera_offset_x
        y = 0
        while y < height:
            pygame.draw.line(screen, player_colour, (x_adjusted, y), (x_adjusted, min(y+dash_length, height)))
            y += dash_length + gap_length

        pygame.display.update()

        if player.x > (2*width)-50:
            H1_end = pygame.time.get_ticks()
            flags_treatment['H1'] = False
            if treatment[0] == 'H1':
                instruction_4_active = True
            elif treatment[1] == 'H1':
                instruction_5_active = True
            elif treatment[2] == 'H1':
                final_screen = True

            # Reset the player's position
            player.x, player.y = player_x, height - (pavement_height/2)
            # Reset the player's target
            target_x, target_y = player.x, player.y
            # Reset the player's velocity
            player_velocity = [0, 0]
            # Reset the bottom flag
            bottom = True
        continue

    if instruction_4_active:
        display_instructions(screen, instructions_text_4)
        continue  
    
    if flags_treatment['H2']:
        if H2_start is None:
            H2_start = pygame.time.get_ticks()

        if moving:
            player_new_x, player_new_y, player_new_vel_x, player_new_vel_y = player.move_towards(
                target_x, target_y, player_velocity[0], player_velocity[1], dt, pedestrian_coords_H2, pedestrian_constants)
            player_velocity = [player_new_vel_x, player_new_vel_y]

            if math.hypot(target_x - player.x, target_y - player.y) < 1:
                moving = False
        
        if bottom:
            if player.y < pavement_height:
                cross_road_H2 += 1
                bottom = False

        elif not bottom:
            if player.y > height - pavement_height:
                cross_road_H2 += 1
                bottom = True
        
        # Save the player and pedestrian positions
        if data_timer >= data_interval:
            player_position_H2.append((player.x, player.y))
            pedestrian_positions_H2.append([(pedestrian.x, pedestrian.y) for pedestrian in pedestrians_H2])
            data_timer = 0

        camera_offset_x = player.x - width/2

        # Pick screen colour
        screen.fill(background_colour)

        # Draw the road
        for rect in rectangles:
            pygame.draw.rect(screen, road_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # Draw the road markings
        for rect in road_markings:
            pygame.draw.rect(screen, road_marking_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # # Draw the curb
        # for rect in curbs:
        #     pygame.draw.rect(screen, curb_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # # Draw the light poles
        # for rect in light_poles:
        #     pygame.draw.rect(screen, light_pole_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # Draw the player
        pygame.draw.circle(screen, player_colour, (int(width/2), int(player.y)), player_radius)
        
        # List of pedestrians that have reached their target/left the screen
        pedestrians_to_remove = []  

        # Update the pedestrians
        for i in range(no_pedestrians):
            pedestrian = pedestrians_H2[i]

            screen_x = pedestrian.x - camera_offset_x

            # Draw the pedestrians
            pygame.draw.circle(screen, pedestrian_colour, (int(screen_x), int(pedestrian.y)), player_radius)

            prev_vel_x, prev_vel_y = pedestrian_velocities_H2[i][0], pedestrian_velocities_H2[i][1]
            ped_target_x, ped_target_y = pedestrian_target_H2[i]

            new_x, new_y, new_vel_x, new_vel_y = pedestrian.move_towards(
                ped_target_x, ped_target_y, prev_vel_x, prev_vel_y, pedestrian_coords_H2, pedestrian_constants
            )

            pedestrian_coords_H2[i] = (new_x, new_y)
            pedestrian_velocities_H2[i] = (new_vel_x, new_vel_y)

            # Check if the pedestrian has reached the target
            # distance_to_target = math.hypot(new_x - ped_target_x, new_y - ped_target_y) 
            if new_x < H2_target_x:
                pedestrians_to_remove.append(i)
            
        # Remove the pedestrians that have reached their target/left the screen
        for i in reversed(pedestrians_to_remove):
            pedestrian_coords_H2.pop(i)
            pedestrian_velocities_H2.pop(i)
            pedestrians_H2.pop(i)
            pedestrian_target_H2.pop(i)
            no_pedestrians -= 1

        if lights_on:
            # Reset the dimmed overlay
            dim_surf.fill((0, 0, 0, dimness))

            # Add the lights
            for light_surf, (x,y) in zip(light_surfaces_H2, light_centres_H2):
                adjusted_x = x - camera_offset_x
                dim_surf.blit(light_surf, (adjusted_x, y), special_flags=pygame.BLEND_RGBA_SUB)
            # Draw the dimmed overlay and lights onto the screen
            screen.blit(dim_surf, (0, 0))

        # Draw the dashed line (target)
        x_adjusted = (width*2)-50 - camera_offset_x
        y = 0
        while y < height:
            pygame.draw.line(screen, player_colour, (x_adjusted, y), (x_adjusted, min(y+dash_length, height)))
            y += dash_length + gap_length

        pygame.display.update()

        if player.x > (2*width)-50:
            H2_end = pygame.time.get_ticks()
            flags_treatment['H2'] = False
            if treatment[0] == 'H2':
                instruction_4_active = True
            elif treatment[1] == 'H2':
                instruction_5_active = True
            elif treatment[2] == 'H2':
                final_screen = True
            
            # Reset the player's position
            player.x, player.y = player_x, height - (pavement_height/2)
            # Reset the player's target
            target_x, target_y = player.x, player.y
            # Reset the player's velocity
            player_velocity = [0, 0]
            # Reset the bottom flag
            bottom = True
            # Reset the number of pedestrians
            no_pedestrians = 40
        continue

    if instruction_5_active:
        display_instructions(screen, instructions_text_5)
        continue

    if flags_treatment['H3']:
        if H3_start is None:
            H3_start = pygame.time.get_ticks()

        if moving:
            player_new_x, player_new_y, player_new_vel_x, player_new_vel_y = player.move_towards(
                target_x, target_y, player_velocity[0], player_velocity[1], dt, pedestrian_coords_H3, pedestrian_constants)
            player_velocity = [player_new_vel_x, player_new_vel_y]

            if math.hypot(target_x - player.x, target_y - player.y) < 1:
                moving = False
        
        if bottom:
            if player.y < pavement_height:
                cross_road_H3 += 1
                bottom = False

        elif not bottom:
            if player.y > height - pavement_height:
                cross_road_H3 += 1
                bottom = True
                
        # Save the player and pedestrian positions
        if data_timer >= data_interval:
            player_position_H3.append((player.x, player.y))
            pedestrian_positions_H3.append([(pedestrian.x, pedestrian.y) for pedestrian in pedestrians_H3])
            data_timer = 0

        camera_offset_x = player.x - width/2

        # Pick screen colour
        screen.fill(background_colour)

        # Draw the road
        for rect in rectangles:
            pygame.draw.rect(screen, road_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # Draw the road markings
        for rect in road_markings:
            pygame.draw.rect(screen, road_marking_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # # Draw the curb
        # for rect in curbs:
        #     pygame.draw.rect(screen, curb_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # # Draw the light poles
        # for rect in light_poles:
        #     pygame.draw.rect(screen, light_pole_colour, (rect[0] - camera_offset_x, rect[1], rect[2], rect[3]))

        # Draw the player
        pygame.draw.circle(screen, player_colour, (int(width/2), int(player.y)), player_radius)
        
        # List of pedestrians that have reached their target/left the screen
        pedestrians_to_remove = []  

        # Update the pedestrians
        for i in range(no_pedestrians):
            pedestrian = pedestrians_H3[i]

            screen_x = pedestrian.x - camera_offset_x

            # Draw the pedestrians
            pygame.draw.circle(screen, pedestrian_colour, (int(screen_x), int(pedestrian.y)), player_radius)

            prev_vel_x, prev_vel_y = pedestrian_velocities_H3[i][0], pedestrian_velocities_H3[i][1]
            ped_target_x, ped_target_y = pedestrian_target_H3[i]

            new_x, new_y, new_vel_x, new_vel_y = pedestrian.move_towards(
                ped_target_x, ped_target_y, prev_vel_x, prev_vel_y, pedestrian_coords_H3, pedestrian_constants
            )

            pedestrian_coords_H3[i] = (new_x, new_y)
            pedestrian_velocities_H3[i] = (new_vel_x, new_vel_y)

            # Check if the pedestrian has reached the target
            if new_x > H3_target_x:
                pedestrians_to_remove.append(i)
            
        # Remove the pedestrians that have reached their target/left the screen
        for i in reversed(pedestrians_to_remove):
            pedestrian_coords_H3.pop(i)
            pedestrian_velocities_H3.pop(i)
            pedestrians_H3.pop(i)
            pedestrian_target_H3.pop(i)
            no_pedestrians -= 1

        if lights_on:
            # Reset the dimmed overlay
            dim_surf.fill((0, 0, 0, dimness))

            # Add the lights
            for light_surf, (x,y) in zip(light_surfaces_H3, light_centres_H3):
                adjusted_x = x - camera_offset_x
                dim_surf.blit(light_surf, (adjusted_x, y), special_flags=pygame.BLEND_RGBA_SUB)
            # Draw the dimmed overlay and lights onto the screen
            screen.blit(dim_surf, (0, 0))

        # Draw the dashed line (target)
        x_adjusted = (width*2)-50 - camera_offset_x
        y = 0
        while y < height:
            pygame.draw.line(screen, player_colour, (x_adjusted, y), (x_adjusted, min(y+dash_length, height)))
            y += dash_length + gap_length
        
        pygame.display.update()

        if player.x > (2*width)-50:
            H3_end = pygame.time.get_ticks()
            flags_treatment['H3'] = False
            if treatment[0] == 'H3':
                instruction_4_active = True
            elif treatment[1] == 'H3':
                instruction_5_active = True
            elif treatment[2] == 'H3':
                final_screen = True
            
            # Reset the player's position
            player.x, player.y = player_x, height - (pavement_height/2)
            # Reset the player's target
            target_x, target_y = player.x, player.y
            # Reset the player's velocity
            player_velocity = [0, 0]
            # Reset the bottom flag
            bottom = True
            # Reset the number of pedestrians
            no_pedestrians = 40
        continue

    if final_screen:
        display_instructions(screen, final_screen_text)
        H1_time = (H1_end - H1_start) / 1000
        H2_time = (H2_end - H2_start) / 1000
        H3_time = (H3_end - H3_start) / 1000

    # Update the display
    pygame.display.update()

# Save the data
save_data(H1_time, H2_time, H3_time, player_position_H1, player_position_H2, player_position_H3, cross_road_H1, 
            cross_road_H2, cross_road_H3, click_H1, click_H2, click_H3, click_position_H1, click_position_H2, 
            click_position_H3, pedestrian_positions_H2, pedestrian_positions_H3, treatment)

# Quit pygame
pygame.quit()
