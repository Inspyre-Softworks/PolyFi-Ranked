from inspyre_splash import auto_splash
from time import sleep


def mock_config_load(delay=5):
    print('Delay')
    sleep(delay)


def get_rand_color():
    import random
    return f'#{random.randint(0, 0xFFFFFF):06x}'


def startup(splash, text_stream, cancel_event):
    splash.add_text(
        'Peek-a-boo',
        position='center',
        font_size=48,
        color=get_rand_color(),
    )
    
    splash.queue_text(
        'Reading config...',
        layer=text_stream, effect='typewriter'        
    )
    mock_config_load()
    
    splash.queue_text(
        'Config ready.',
        layer=text_stream, effect='fade_in', direction='bottom'
    )
    
    splash.queue_text(
        'Initializing modules...',
        layer=text_stream, effect='typewriter'
    )
    mock_config_load()
    
    splash.set_status('Starting services...')



splash = auto_splash(name='intro')
text_stream = splash.add_text_sequence(position='bottom', y_offset=92)
splash.run_until(startup, splash, text_stream, cancel_kwarg='cancel_event')
