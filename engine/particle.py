
from .ecs import *


class Particle:

    def __init__(self):
        self.size = 20
        self.pos = glm.vec3(0, random.uniform(-0.01, 0.01), 0)
        self.color = glm.vec4(random.choice([0, 1]), random.choice([0, 1]), random.choice([0, 1]), 0.1)
        self.dir = random.uniform(-0.1, 0.1)
        self.lifetime = 0.4

    def process(self):
        self.lifetime -= Clock.dt
        self.color.w -= 0.3 * Clock.dt
        self.pos.y -= 0.2 * Clock.dt
        self.pos.x += self.dir * Clock.dt


class ParticleSystem:

    def __init__(self, n: int):
        self.max_particles = n
        self.particles = [Particle() for _ in range(n)]

    def process(self):
        for p in self.particles:
            p.process()
            if p.lifetime < 0:
                self.particles.remove(p)
                p = Particle()
                self.particles.append(p)
    
    def render(self):
        for p in self.particles:
            Renderer.draw_point(p.size, p.pos.x, p.pos.y, p.pos.z, p.color.x, p.color.y, p.color.z, p.color.w)