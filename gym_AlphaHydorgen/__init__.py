from gym.envs.registration import register

register(
    id='AlphaHydorgen-v0',
    entry_point='gym_AlphaHydorgen.envs:AlphaHydorgen',
)