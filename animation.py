import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

# Dark blue background from your presentation
dark_blue = "#0d1b2a"

def symmetrical_converging_range(values):
    result = []
    left = 0
    right = len(values) - 1
    while left <= right:
        if right != left:
            result.append(values[right])
        result.append(values[left])
        left += 1
        right -= 1
    return result

# Define routine ranges
temperature_range = list(range(20, 41, 4))
humidity_range = list(range(60, 39, -4))
temp_waypoints = symmetrical_converging_range(temperature_range)
humid_waypoints = symmetrical_converging_range(humidity_range)
waypoints = [(temp, humid) for humid in humid_waypoints for temp in temp_waypoints]

# Extract data
temps = [wp[0] for wp in waypoints]
hums = [wp[1] for wp in waypoints]
steps = np.arange(1, len(temps) + 1)

# Simulate hold at each step
hold_frames_per_step = 4
held_temps = []
held_hums = []
held_steps = []

for i, (t, h) in enumerate(zip(temps, hums), start=1):
    held_temps.extend([t] * hold_frames_per_step)
    held_hums.extend([h] * hold_frames_per_step)
    held_steps.extend([i] * hold_frames_per_step)

# Plot setup
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), facecolor=dark_blue)
fig.subplots_adjust(hspace=0.4)

# Temperature plot
ax1.set_facecolor(dark_blue)
temp_line, = ax1.plot([], [], 'o-', color='cyan')
ax1.set_xlim(1, len(temps))
ax1.set_ylim(min(temps) - 2, max(temps) + 2)
ax1.set_title("Temperature Waypoints Over Routine Steps", color='white')
ax1.set_ylabel("Temperature (°C)", color='white')
ax1.tick_params(colors='white')
ax1.grid(True, color='gray', linestyle='--')

# Humidity plot
ax2.set_facecolor(dark_blue)
humid_line, = ax2.plot([], [], 's-', color='lime')
ax2.set_xlim(1, len(hums))
ax2.set_ylim(min(hums) - 5, max(hums) + 5)
ax2.set_title("Humidity Waypoints Over Routine Steps", color='white')
ax2.set_xlabel("Step", color='white')
ax2.set_ylabel("Humidity (%)", color='white')
ax2.tick_params(colors='white')
ax2.grid(True, color='gray', linestyle='--')

# Animate update
def update(frame):
    temp_line.set_data(held_steps[:frame], held_temps[:frame])
    humid_line.set_data(held_steps[:frame], held_hums[:frame])
    return temp_line, humid_line

ani = animation.FuncAnimation(fig, update, frames=len(held_steps) + 1, interval=200, blit=True, repeat=False)

# Save it
ani.save("routine_waypoints_animation_dark_blue.mp4", writer='ffmpeg', fps=5)