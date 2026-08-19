"""
Groove Trainer — sample-accurate groove practice for Windows.
Requires: pip install PyQt6 numpy sounddevice Pillow
100% offline. Boutique exotic-wood UI + original GrooveTrainerSetup.exe drum synthesis.
"""

from __future__ import annotations

import base64
import io
import sys
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QLocale, QObject, QPointF, QRect, QRectF, QSettings, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

SAMPLE_RATE = 48_000
CHANNELS = 2
BLOCKSIZE = 256
PATTERN_LEN = 8
APP_VERSION = "1.0.1"

STYLE_JAZZ = "jazz"
STYLE_FUNK = "funk"
STYLE_ROCK = "rock"
STYLE_FUSION = "fusion"
STYLE_MOTOWN = "motown"

SUBDIVISION_QUARTERS = "Quarter Notes"
SUBDIVISION_EIGHTHS = "Eighth Notes"

POCKET_BEHIND = "Laid Back"
POCKET_CENTER = "In the Pocket"
POCKET_AHEAD = "Ahead / Driving"

ANTON_LAID = ("Anton Shcherbakov (Laid Back)", -8)
ANTON_CENTER = ("Anton Shcherbakov (Center)", -1)
ANTON_AHEAD = ("Anton Shcherbakov (Ahead)", 2)
ANTON_DISPLAY = "Anton Shcherbakov (Bass Player from Chelyabinsk)"
ANTON_DISPLAY_RU = "Anton Shcherbakov (бас-гитарист из Челябинска)"

GENRE_PRESETS = {
    STYLE_JAZZ: {
        POCKET_BEHIND: [
            ("Paul Chambers", -10),
            ("Ron Carter", -14),
            ("Charlie Haden", -18),
        ],
        POCKET_CENTER: [
            ("Ray Brown", 0),
            ("Christian McBride", 0),
            ("Oscar Pettiford", 2),
        ],
        POCKET_AHEAD: [
            ("Niels-Henning Ørsted Pedersen", 12),
            ("Scott LaFaro", 10),
        ],
    },
    STYLE_FUNK: {
        POCKET_BEHIND: [
            ("Bootsy Collins", -22),
            ("Larry Graham", -15),
            ("George Porter Jr.", -18),
        ],
        POCKET_CENTER: [
            ("Louis Johnson", 0),
            ("Verdine White", 0),
            ("Rocco Prestia", 3),
        ],
        POCKET_AHEAD: [
            ("Flea", 10),
            ("Robert Trujillo", 8),
        ],
    },
    STYLE_ROCK: {
        POCKET_BEHIND: [
            ("John Entwistle", -8),
            ("Geezer Butler", -12),
            ("Roger Waters", -15),
        ],
        POCKET_CENTER: [
            ("John Paul Jones", -2),
            ("Geddy Lee", 0),
            ("Michael Anthony", 0),
        ],
        POCKET_AHEAD: [
            ("Cliff Burton", 22),
            ("Jason Newsted", 24),
            ("Lemmy Kilmister", 20),
        ],
    },
    STYLE_FUSION: {
        POCKET_BEHIND: [
            ("Jimmy Haslip", -12),
            ("Gary Willis", -10),
            ("Lincoln Goines", -8),
            ANTON_LAID,
        ],
        POCKET_CENTER: [
            ("Victor Wooten", 0),
            ("Richard Bona", 0),
            ("Matthew Garrison", 2),
            ANTON_CENTER,
        ],
        POCKET_AHEAD: [
            ("Jaco Pastorius", 14),
            ("Hadrien Feraud", 12),
            ("Anton Davidyants", 15),
            ANTON_AHEAD,
        ],
    },
    STYLE_MOTOWN: {
        POCKET_BEHIND: [
            ('Donald "Duck" Dunn', -15),
            ("James Jamerson", -12),
            ("Carol Kaye (Laid Back Feel)", -5),
            ("Pino Palladino (D'Angelo Era)", -18),
            ANTON_LAID,
        ],
        POCKET_CENTER: [
            ("Nathan East", 0),
            ("Carol Kaye (Center)", 0),
            ("Marcus Miller (Pop Feel)", 4),
            ANTON_CENTER,
        ],
        POCKET_AHEAD: [
            ("Pino Palladino (John Mayer Trio Era)", 6),
            ("Sting", 10),
            ANTON_AHEAD,
        ],
    },
}

GROOVE_BIOS = {
    "Paul Chambers": (
        "The definitive walking-bass swing. Delivers a relaxed, lazy low-end pulse "
        "that drags slightly behind the ride cymbal, breathing massive acoustic air "
        "into modern jazz trios."
    ),
    "Ron Carter": (
        "Intellectual jazz heavy-pocket. Delivers an elegant, comfortable delay on "
        "the downbeats, grounding avant-garde movements with deep rhythmic stability."
    ),
    "Charlie Haden": (
        "Poetic avant-garde space. Delivers an extreme, resonant behind-the-beat weight "
        "that leaves vast harmonic space open for horn lines and solos."
    ),
    "Anton Shcherbakov (Laid Back)": (
        "Modern progressive pocket. Delivers a heavy, calculated contemporary relaxation "
        "feel to the low-end, keeping the track stable but deeply groovy."
    ),
    "Ray Brown": (
        "The baseline of swing perfection. Sits dead-center at absolute zero, delivering "
        "a pristine, concrete-like foundational pulse that acts as the ultimate jazz timekeeper."
    ),
    "Christian McBride": (
        "Modern acoustic authority. Delivers a robust, perfectly quantized central anchor "
        "with ferocious fingerstyle dynamic power."
    ),
    "Oscar Pettiford": (
        "Bop-era crisp precision. Locks firmly into the middle of the beat with a subtle "
        "forward weight that drives acoustic combos cleanly."
    ),
    "Anton Shcherbakov (Center)": (
        "Absolute pristine studio quantization. Locks completely with the core drum "
        "transient, delivering a rock-solid, concrete-like foundational anchor."
    ),
    "Niels-Henning Ørsted Pedersen": (
        "European fusion virtuosity. Delivers an intense, lightning-fast forward momentum "
        "that pushes the drummer and accelerates ensemble energy."
    ),
    "Scott LaFaro": (
        "Airy dialogue propulsion. Pushes the front edge of the beat, transforming the "
        "upright bass into a driving, fluidly leading melodic voice."
    ),
    "Anton Shcherbakov (Ahead)": (
        "Dynamic micro-propulsion. Delivers an intense, snappy forward momentum that sits "
        "right at the front tooth of the drum attack, driving the push from Chelyabinsk."
    ),
    "Bootsy Collins": (
        "The greasy rubber-band funk pocket. Delivers an immense, heavily dragging "
        "syncopation that sits far behind the kick, making the groove feel loose, low, "
        "and deeply danceable."
    ),
    "Larry Graham": (
        "The slap-bass Genesis pocket. Delivers a heavy thumb-thump that pulls back "
        "slightly, giving the slaps a massive weight before horns and vocals hit."
    ),
    "George Porter Jr.": (
        "New Orleans swamp groove. Delivers a highly relaxed, syrupy laid-back pulse that "
        "lets the track lean back comfortably without losing structural momentum."
    ),
    "Louis Johnson": (
        "The Thunder-Thumbs studio engine. Sits precisely at zero, firing aggressive, "
        "high-velocity slaps that cement pop and funk tracks with perfect grid accuracy."
    ),
    "Verdine White": (
        "Disco-funk kinetic locomotive. Delivers a pristine, centered, highly animated "
        "performance that anchors explosive brass sections seamlessly."
    ),
    "Rocco Prestia": (
        "Muted 16th-note percussive machine. Sits in the center with a micro-lean forward, "
        "driving continuous tight fingerstyle pulses."
    ),
    "Flea": (
        "High-octane funk-rock ignition. Delivers an explosive forward propulsion that "
        "rushes the drum transients, injecting raw, stadium-filling punk energy into the "
        "funk grid."
    ),
    "Robert Trujillo": (
        "Heavy fingerstyle assault. Pushes right before the kick transient, delivering an "
        "intense, hard-hitting rhythmic engine that drives heavy modern funk."
    ),
    "John Entwistle": (
        "The thundering rock-lead weight. Sits slightly behind the chaotic drums, generating "
        "a massive, overdriven low-end wall that grounds stadium rock."
    ),
    "Geezer Butler": (
        "Heavy metal doom anchor. Delivers a dark, sludge-like laid-back pulse that drags "
        "behind the beat, creating an intimidatingly heavy rhythmic floor."
    ),
    "Roger Waters": (
        "Hypnotic progressive spaciousness. Delivers a slow, deeply calculated delay that "
        "anchors psychedelic textures with patient, steady momentum."
    ),
    "John Paul Jones": (
        "The ultimate classic rock cement. Sits flawlessly in the middle of the beat, "
        "fusing on a sub-atomic level with the heavy kick to build an unbreakable rock "
        "foundation."
    ),
    "Geddy Lee": (
        "Progressive power-trio precision. Delivers hyper-accurate, pristine timing at "
        "absolute zero, leaving room for complex synthesizers and polyrhythms."
    ),
    "Michael Anthony": (
        "Hard-rock arena anchor. Delivers an unwavering central pulse, providing a "
        "rock-solid, dependable floor while guitars and vocals soar."
    ),
    "Cliff Burton": (
        "Thrash metal distortion drive. Heavily pushes ahead of the drums with furious "
        "classical-infused fingerstyle picking, turning the bass into a front-line "
        "battering ram."
    ),
    "Jason Newsted": (
        "Relentless pick-attack violence. Drives far ahead of the beat with heavy "
        "down-picking, generating an intense, rushing forward momentum that forces the "
        "metal pulse forward."
    ),
    "Lemmy Kilmister": (
        "Ripped Rickenbacker power-chord engine. Pushes aggressively ahead of the drums, "
        "blurring the line between bass and rhythm guitar with raw speed."
    ),
    "Jimmy Haslip": (
        "Liquid left-handed elegance. Delivers a smooth, highly melodic laid-back pulse "
        "that softens sharp fusion syncopations with sophisticated phrasing."
    ),
    "Gary Willis": (
        "Fretless fluid-dynamics. Employs a unique multi-finger light touch that sits "
        "comfortably behind the beat, adding an organic, breathing weight to complex "
        "fusion charts."
    ),
    "Lincoln Goines": (
        "Afro-Cuban fusion bridge. Sits relaxed behind the snare line, anchoring complex "
        "syncopated Latin jazz structures with urban groove weight."
    ),
    "Victor Wooten": (
        "Absolute rhythmic mastery. Sits at absolute zero, providing mechanical grid "
        "perfection that allows complex open-hammer-pluck techniques to sound fluid and "
        "flawless."
    ),
    "Richard Bona": (
        "Vocalized lyrical precision. Combines pristine central quantization with a "
        "smooth, warm singing fingerstyle that locks perfectly into international jazz "
        "matrices."
    ),
    "Matthew Garrison": (
        "Four-finger dense chord propulsion. Sits dead center with a microscopic forward "
        "tilt, weaving complex harmonic webs right at the core of the pulse."
    ),
    "Jaco Pastorius": (
        "The bridge-pickup revolution. Pushes aggressively ahead of the beat, utilizing "
        "bright, growling staccato lines to lead the ensemble from the front of the groove."
    ),
    "Hadrien Feraud": (
        "Modern fluid virtuosic drive. Fires intense forward-leaning staccato lines that "
        "push the boundaries of fusion speed, generating incredible forward momentum."
    ),
    "Anton Davidyants": (
        "Surgical articulation fury. Pushes hard at the front edge of the transient; every "
        "single note fires like a precise bullet, driving complex modern fusion with "
        "staggering energetic propulsion."
    ),
    'Donald "Duck" Dunn': (
        "Stax Records soul anchor. Delivers a heavy, unhurried Memphis pocket that sits "
        "comfortably behind the snare, locking horns and vocals into classic radio-soul weight."
    ),
    "James Jamerson": (
        "The absolute Motown definition of pocket weight. Melodic eighth-note lines lean "
        "behind the kick, giving Hitsville tracks that famous, breathing low-end gravity."
    ),
    "Carol Kaye (Laid Back Feel)": (
        "Driving studio pick precision with a slight pull-back weight. Session-perfect "
        "articulation that still leaves air behind the drum transient."
    ),
    "Nathan East": (
        "Pristine, ultra-accurate Eric Clapton / Daft Punk pop session perfection. "
        "Dead-center quantization with a polished, broadcast-ready low end."
    ),
    "Carol Kaye (Center)": (
        "Hyper-precise downbeat studio master. Locks the Wrecking Crew grid at absolute "
        "zero so vocals, strings, and drums sit on one camera-ready click."
    ),
    "Marcus Miller (Pop Feel)": (
        "Snappy modern slap precision. A slight forward lean that keeps radio-pop choruses "
        "tight without rushing the backbeat."
    ),
    "Pino Palladino (John Mayer Trio Era)": (
        "Pushing forward with energetic, tight pick-groove propulsion. Trio-era Pino "
        "drives the pocket ahead of the kit while staying surgically in the song."
    ),
    "Pino Palladino (D'Angelo Era)": (
        "D'Angelo-era laid-back rubber-band pocket. Melodic, behind-the-beat lines that "
        "lean into the snare and leave the groove breathing like Voodoo-era session bass."
    ),
    "Sting": (
        "Driving, syncopated reggae-pop forward energy. Pushes the drums from the front "
        "of the beat with springy, vocal-minded bass lines."
    ),
}

GROOVE_BIOS_RU = {
    "Paul Chambers": (
        "Эталонный walking-бас свинга. Расслабленный ленивый пульс низа слегка "
        "отстаёт от райда и даёт джазовому трио живой акустический воздух."
    ),
    "Ron Carter": (
        "Интеллектуальный джазовый карман. Элегантная задержка на сильных долях "
        "держит авангард на глубокой ритмической опоре."
    ),
    "Charlie Haden": (
        "Поэтический авангардный простор. Крайне резонирующий вес позади доли "
        "оставляет огромное гармоническое пространство для духовых и соло."
    ),
    "Anton Shcherbakov (Laid Back)": (
        "Современный прогрессивный карман. Тяжёлое, точно рассчитанное расслабление "
        "низа: трек стабилен, но глубоко грувит."
    ),
    "Ray Brown": (
        "Нулевая точка свинга. Сидит мёртво в центре, даёт бетонный фундамент — "
        "главный джазовый хранитель времени."
    ),
    "Christian McBride": (
        "Современная акустическая власть. Мощный, идеально квантованный якорь "
        "с яростной динамикой пальцевого штриха."
    ),
    "Oscar Pettiford": (
        "Боп-точность. Плотно в середине доли с лёгким наклоном вперёд, "
        "чисто двигает акустические составы."
    ),
    "Anton Shcherbakov (Center)": (
        "Студийная квантизация. Полностью совпадает с атакой бочки и даёт "
        "бетонный, абсолютно устойчивый фундамент."
    ),
    "Niels-Henning Ørsted Pedersen": (
        "Европейский фьюжн-виртуоз. Молниеносный импульс вперёд, который "
        "подталкивает барабанщика и разгоняет ансамбль."
    ),
    "Scott LaFaro": (
        "Воздушный диалог. Толкает передний край доли и превращает контрабас "
        "в ведущий мелодический голос."
    ),
    "Anton Shcherbakov (Ahead)": (
        "Динамический микро-импульс. Хлёсткий вынос на самый зуб атаки ударных — "
        "драйв из Челябинска."
    ),
    "Bootsy Collins": (
        "Жирный резиновый фанк-карман. Огромная синкопа далеко позади бочки: "
        "грув становится свободным, низким и танцевальным."
    ),
    "Larry Graham": (
        "Генезис слэпа. Тяжёлый большой палец чуть оттягивает долю, "
        "давая шлепкам вес до входа духовых и вокала."
    ),
    "George Porter Jr.": (
        "Болотный грув Нового Орлеана. Сиропный, очень расслабленный пульс: "
        "трек откидывается назад, не теряя конструкции."
    ),
    "Louis Johnson": (
        "Студийный мотор Thunder-Thumbs. Точно в нуле, агрессивные быстрые слэпы "
        "цементируют поп и фанк по сетке."
    ),
    "Verdine White": (
        "Диско-фанк локомотив. Чистый, центрированный, очень живой пульс, "
        "на который садятся взрывные духовые."
    ),
    "Rocco Prestia": (
        "Приглушённая перкуссионная машина шестнадцатыми. В центре с микро-наклоном "
        "вперёд — непрерывный плотный пальцевой пульс."
    ),
    "Flea": (
        "Высокооктановый фанк-рок. Взрывной вынос к атаке ударных — сырая "
        "стадионная панк-энергия внутри фанк-сетки."
    ),
    "Robert Trujillo": (
        "Тяжёлый пальцевой штурм. Давит прямо перед атакой бочки — жёсткий "
        "ритмический двигатель современного фанка."
    ),
    "John Entwistle": (
        "Громовой рок-лид. Чуть позади хаоса ударных строит огромную "
        "перегруженную стену низа, на которой стоит стадионный рок."
    ),
    "Geezer Butler": (
        "Дум-якорь хеви-метала. Тёмный, тягучий пульс позади доли — "
        "устрашающе тяжёлый ритмический пол."
    ),
    "Roger Waters": (
        "Гипнотический прогрессивный простор. Медленная, точно выверенная задержка "
        "якорит психоделические фактуры терпеливым импульсом."
    ),
    "John Paul Jones": (
        "Цемент классического рока. Идеально в середине доли, срастается с бочкой "
        "на субатомном уровне — неломаемый фундамент."
    ),
    "Geddy Lee": (
        "Точность пауэр-трио. Сверхточная, кристальная квантизация в абсолютном нуле, "
        "чтобы осталось место синтезаторам и полиритмии."
    ),
    "Michael Anthony": (
        "Хард-рок арена-якорь. Несгибаемый центральный пульс — надёжный пол, "
        "пока гитары и вокал улетают вверх."
    ),
    "Cliff Burton": (
        "Трэш с дисторшном. Сильно впереди ударных, яростный классический пальцевой "
        "штрих превращает бас в таран первой линии."
    ),
    "Jason Newsted": (
        "Непрерывный медиаторный натиск. Далеко впереди доли, тяжёлый даунстрок "
        "гонит металлический пульс вперёд."
    ),
    "Lemmy Kilmister": (
        "Рваный Rickenbacker в пауэраккордах. Агрессивно впереди ударных, "
        "стирает границу между басом и ритм-гитарой."
    ),
    "Jimmy Haslip": (
        "Жидкая леворукая элегантность. Гладкий мелодичный пульс позади доли "
        "смягчает острые фьюжн-синкопы изысканной фразировкой."
    ),
    "Gary Willis": (
        "Безладовая гидродинамика. Лёгкий многопальцевый штрих удобно сидит "
        "позади доли и даёт сложным фьюжн-картам живое дыхание."
    ),
    "Lincoln Goines": (
        "Афро-кубинский мост. Расслабленно позади малого, якорит сложные "
        "латинские джазовые синкопы городским весом грува."
    ),
    "Victor Wooten": (
        "Абсолютное ритмическое мастерство. Мёртвый ноль, механическая сетка, "
        "на которой сложный open-hammer-pluck звучит текуче и безупречно."
    ),
    "Richard Bona": (
        "Вокальная лирическая точность. Чистая центральная квантизация и тёплый "
        "поющий пальцевой штрих, идеально входящий в мировые джазовые матрицы."
    ),
    "Matthew Garrison": (
        "Плотные четырёхпальцевые аккорды. Мёртвый центр с микроскопическим наклоном "
        "вперёд — гармонические сети в самом ядре пульса."
    ),
    "Jaco Pastorius": (
        "Революция бриджевого датчика. Агрессивно впереди доли, яркие рычащие "
        "стаккато ведут ансамбль с переднего края грува."
    ),
    "Hadrien Feraud": (
        "Современный текучий драйв. Плотные стаккато с наклоном вперёд на пределе "
        "фьюжн-скорости — огромный импульс движения."
    ),
    "Anton Davidyants": (
        "Хирургическая артикуляция. Жёстко на переднем крае атаки: каждая нота "
        "бьёт как пуля и гонит сложный современный фьюжн."
    ),
    'Donald "Duck" Dunn': (
        "Якорь Stax. Тяжёлый неторопливый мемфисский карман позади малого, "
        "сажает духовые и вокал в классический радио-соул."
    ),
    "James Jamerson": (
        "Само определение мотауновского кармана. Мелодичные восьмые опираются "
        "позади бочки и дают хитам Hitsville знаменитую дышащую гравитацию низа."
    ),
    "Carol Kaye (Laid Back Feel)": (
        "Студийная медиаторная точность с лёгким оттягиванием. Сессионно идеальная "
        "артикуляция, но с воздухом позади атаки ударных."
    ),
    "Nathan East": (
        "Безупречная поп-сессия Eric Clapton / Daft Punk. Мёртвый центр "
        "и полированный эфирный низ."
    ),
    "Carol Kaye (Center)": (
        "Студийный мастер сильной доли. Сетка Wrecking Crew в абсолютном нуле — "
        "вокал, струнные и ударные на одном клике."
    ),
    "Marcus Miller (Pop Feel)": (
        "Хлёсткий современный слэп. Лёгкий наклон вперёд держит радио-поп припевы "
        "плотными, не торопя бэкбит."
    ),
    "Pino Palladino (John Mayer Trio Era)": (
        "Энергичный плотный медиаторный драйв. Трио-эра Пино толкает карман "
        "впереди установки, оставаясь хирургически в песне."
    ),
    "Pino Palladino (D'Angelo Era)": (
        "Резиновый карман эры D'Angelo. Мелодичные линии позади доли опираются "
        "в малый и дышат, как сессионный бас Voodoo."
    ),
    "Sting": (
        "Синкопированная регги-поп энергия. Толкает ударные с переднего края доли "
        "пружинистыми, вокальными басовыми линиями."
    ),
}


def groove_bio(name: str) -> str:
    pack = GROOVE_BIOS_RU if APP_LANG == "ru" else GROOVE_BIOS
    return pack.get(name, GROOVE_BIOS[name])

POCKET_ROLES = {
    POCKET_BEHIND: "behind",
    POCKET_CENTER: "center",
    POCKET_AHEAD: "ahead",
}

POCKET_TINTS = {
    POCKET_BEHIND: "behind",
    POCKET_CENTER: "center",
    POCKET_AHEAD: "ahead",
}

THEME_CYAN = "#00e5ff"
THEME_CYAN_SOFT = "#7af4ff"
THEME_GOLD = "#ffb703"
THEME_GOLD_SOFT = "#e8c37a"
THEME_INK = "#0a0908"

POCKET_WOOD = {
    POCKET_BEHIND: "redwood_burl",
    POCKET_CENTER: "eye_poplar",
    POCKET_AHEAD: "spalted_maple",
}

POCKET_INLAY = {
    POCKET_BEHIND: "#8b3a32",
    POCKET_CENTER: "#7a6a52",
    POCKET_AHEAD: "#c49030",
}

STYLE_LABELS = {
    STYLE_JAZZ: "JAZZ",
    STYLE_FUNK: "FUNK",
    STYLE_ROCK: "ROCK",
    STYLE_FUSION: "FUSION",
    STYLE_MOTOWN: "MOTOWN & POP",
}

STYLE_DESCRIPTIONS = {
    STYLE_JAZZ: "Acoustic swing clock · closed hat 1 / 2-and / 3 / 4-and · hat chicks on 2 & 4 · soft quarter kick",
    STYLE_FUNK: "Straight funk clock · kick 1/4/11 · snare 5 & 13 · alternating hats · no ghost snares",
    STYLE_ROCK: "Straight rock clock · kick 1 & 9 · snare 5 & 13 · closed hats on odd 16ths",
    STYLE_FUSION: "Straight-ahead fusion clock · kick 1 & 9 · snare 5 & 13 · acoustic ride-bell accents",
    STYLE_MOTOWN: "Radio-pop pocket · kick 1/5/8/9/13 · snare 5 & 13 · closed hats on odd 16ths · open hat lift on 16",
}

STYLE_DESCRIPTIONS_RU = {
    STYLE_JAZZ: "Акустический свинг · закрытый хэт 1 / 2-и / 3 / 4-и · чики хэта на 2 и 4 · мягкая четвертная бочка",
    STYLE_FUNK: "Прямой фанк · бочка 1/4/11 · малый 5 и 13 · чередующиеся хэты · без гоустов на малом",
    STYLE_ROCK: "Прямой рок · бочка 1 и 9 · малый 5 и 13 · закрытый хэт на нечётных шестнадцатых",
    STYLE_FUSION: "Прямой фьюжн · бочка 1 и 9 · малый 5 и 13 · акценты колокольчика райда",
    STYLE_MOTOWN: "Радио-поп карман · бочка 1/5/8/9/13 · малый 5 и 13 · закрытый хэт на нечётных 16-х · открытый хэт на 16",
}

APP_LANG = "en"
APP_SKIN = "photo"

UI_STRINGS = {
    "en": {
        "window_title": "Groove Trainer",
        "brand": "Groove Trainer",
        "header_by": "Groove and Microtiming Trainer Kit by",
        "skin_photo": "PHOTO",
        "skin_gen": "GEN",
        "skin_photo_tip": "Photographic woods",
        "skin_gen_tip": "Generated woods — same glass, glow, and finish",
        "transport": "Transport",
        "start": "▶  START",
        "stop": "■  STOP",
        "clear": "CLEAR ANALYZER",
        "beat_matrix": "Beat Matrix",
        "pocket_audio": "Pocket & Audio",
        "metro_grid": "Metronome Grid",
        "micro_offset": "Micro-Timing Offset",
        "offset_hint": "Negative = behind · Positive = ahead",
        "audio_levels": "Audio Levels",
        "drums": "Drums",
        "metronome": "Metronome",
        "click_pitch": "Click Pitch",
        "quarters": "Quarter Notes",
        "eighths": "Eighth Notes",
        "kicker": "GROOVE ANALYZER  ·  POCKET REPORT",
        "select_musician": "Select a musician",
        "tab_genre": "TAB GENRE",
        "no_profile": "no profile loaded",
        "idle_bio": (
            "Choose a legendary pocket from the grid below. The analyzer will explain "
            "exactly what that millisecond placement delivers to the music — the weight, "
            "the delay, and the way the low end sits against the kit."
        ),
        "pocket_behind": "Laid Back",
        "pocket_center": "In the Pocket",
        "pocket_ahead": "Ahead / Driving",
        "pocket_short_behind": "Laid Back",
        "pocket_short_center": "Center",
        "pocket_short_ahead": "Ahead",
        "tab_jazz": "JAZZ",
        "tab_funk": "FUNK",
        "tab_rock": "ROCK",
        "tab_fusion": "FUSION",
        "tab_motown": "MOTOWN & POP",
    },
    "ru": {
        "window_title": "Groove Trainer",
        "brand": "Groove Trainer",
        "header_by": "Набор для тренировки грува и микротайминга —",
        "skin_photo": "ФОТО",
        "skin_gen": "ГЕН",
        "skin_photo_tip": "Фотографический шпон",
        "skin_gen_tip": "Сгенерированные текстуры — те же стекло, свечение и лак",
        "transport": "Транспорт",
        "start": "▶  СТАРТ",
        "stop": "■  СТОП",
        "clear": "СБРОСИТЬ АНАЛИЗАТОР",
        "beat_matrix": "Матрица долей",
        "pocket_audio": "Карман и звук",
        "metro_grid": "Сетка метронома",
        "micro_offset": "Смещение микротайминга",
        "offset_hint": "Минус — сзади · Плюс — впереди",
        "audio_levels": "Уровни",
        "drums": "Барабаны",
        "metronome": "Метроном",
        "click_pitch": "Высота клика",
        "quarters": "Четверти",
        "eighths": "Восьмые",
        "kicker": "АНАЛИЗАТОР ГРУВА  ·  ОТЧЁТ О КАРМАНЕ",
        "select_musician": "Выберите музыканта",
        "tab_genre": "ЖАНР ВКЛАДКИ",
        "no_profile": "профиль не выбран",
        "idle_bio": (
            "Выберите легендарный карман в сетке ниже. Анализатор объяснит, "
            "что именно даёт это смещение в миллисекундах — вес, задержку "
            "и то, как низ садится относительно ударных."
        ),
        "pocket_behind": "Сзади",
        "pocket_center": "В кармане",
        "pocket_ahead": "Впереди",
        "pocket_short_behind": "Сзади",
        "pocket_short_center": "Центр",
        "pocket_short_ahead": "Впереди",
        "tab_jazz": "ДЖАЗ",
        "tab_funk": "ФАНК",
        "tab_rock": "РОК",
        "tab_fusion": "ФЬЮЖН",
        "tab_motown": "МОТАУН И ПОП",
    },
}

TAB_I18N = {
    STYLE_JAZZ: "tab_jazz",
    STYLE_FUNK: "tab_funk",
    STYLE_ROCK: "tab_rock",
    STYLE_FUSION: "tab_fusion",
    STYLE_MOTOWN: "tab_motown",
}

POCKET_I18N = {
    POCKET_BEHIND: "pocket_behind",
    POCKET_CENTER: "pocket_center",
    POCKET_AHEAD: "pocket_ahead",
}

POCKET_SHORT_I18N = {
    POCKET_BEHIND: "pocket_short_behind",
    POCKET_CENTER: "pocket_short_center",
    POCKET_AHEAD: "pocket_short_ahead",
}


def t(key: str) -> str:
    pack = UI_STRINGS.get(APP_LANG, UI_STRINGS["en"])
    return pack.get(key, UI_STRINGS["en"][key])


def anton_display() -> str:
    return ANTON_DISPLAY_RU if APP_LANG == "ru" else ANTON_DISPLAY


def style_description(style: str) -> str:
    if APP_LANG == "ru":
        return STYLE_DESCRIPTIONS_RU[style]
    return STYLE_DESCRIPTIONS[style]


def style_tab_label(style: str) -> str:
    return t(TAB_I18N[style])


def pocket_title(pocket: str) -> str:
    return t(POCKET_I18N[pocket])


def pocket_short(pocket: str) -> str:
    return t(POCKET_SHORT_I18N[pocket])


def current_style_label(style: str) -> str:
    return style_tab_label(style)

SWING_AND = 2.0 / 3.0
STEPS_16 = 16
KIT_KICK = "kick"
KIT_SNARE = "snare"
KIT_HAT_CLOSED = "hat_closed"
KIT_HAT_OPEN = "hat_open"
KIT_RIDE = "ride"
CHOKE_FADE = max(8, int(0.006 * SAMPLE_RATE))


@dataclass(frozen=True)
class Hit:
    beat: float
    sound: str
    velocity: float


def _step_beat(step_1based: int) -> float:
    return (step_1based - 1) / 4.0


def _jazz_pattern() -> tuple[Hit, ...]:
    return (
        Hit(0.0, KIT_HAT_CLOSED, 1.00),
        Hit(1.0 + SWING_AND, KIT_HAT_CLOSED, 1.00),
        Hit(2.0, KIT_HAT_CLOSED, 1.00),
        Hit(3.0 + SWING_AND, KIT_HAT_CLOSED, 1.00),
        Hit(1.0, KIT_HAT_CLOSED, 1.00),
        Hit(3.0, KIT_HAT_CLOSED, 1.00),
        Hit(0.0, KIT_KICK, 0.22),
        Hit(1.0, KIT_KICK, 0.22),
        Hit(2.0, KIT_KICK, 0.22),
        Hit(3.0, KIT_KICK, 0.22),
    )


def _funk_pattern() -> tuple[Hit, ...]:
    hits: list[Hit] = [
        Hit(_step_beat(1), KIT_KICK, 1.00),
        Hit(_step_beat(4), KIT_KICK, 1.00),
        Hit(_step_beat(11), KIT_KICK, 1.00),
        Hit(_step_beat(5), KIT_SNARE, 1.00),
        Hit(_step_beat(13), KIT_SNARE, 1.00),
    ]
    for step in range(1, STEPS_16 + 1):
        sound = KIT_HAT_CLOSED if step % 2 == 1 else KIT_HAT_OPEN
        hits.append(Hit(_step_beat(step), sound, 1.00))
    return tuple(hits)


def _rock_pattern() -> tuple[Hit, ...]:
    hits: list[Hit] = [
        Hit(_step_beat(1), KIT_KICK, 1.00),
        Hit(_step_beat(9), KIT_KICK, 1.00),
        Hit(_step_beat(5), KIT_SNARE, 1.00),
        Hit(_step_beat(13), KIT_SNARE, 1.00),
    ]
    for step in (1, 3, 5, 7, 9, 11, 13, 15):
        hits.append(Hit(_step_beat(step), KIT_HAT_CLOSED, 1.00))
    return tuple(hits)


def _fusion_pattern() -> tuple[Hit, ...]:
    hits: list[Hit] = [
        Hit(_step_beat(1), KIT_KICK, 1.00),
        Hit(_step_beat(3), KIT_KICK, 1.00),
        Hit(_step_beat(7), KIT_KICK, 1.00),
        Hit(_step_beat(11), KIT_KICK, 1.00),
        Hit(_step_beat(14), KIT_KICK, 1.00),
        Hit(_step_beat(5), KIT_SNARE, 1.00),
        Hit(_step_beat(12), KIT_SNARE, 1.00),
        Hit(_step_beat(5), KIT_HAT_CLOSED, 1.00),
        Hit(_step_beat(13), KIT_HAT_CLOSED, 1.00),
    ]
    for step in (1, 3, 5, 7, 9, 11, 13, 15):
        hits.append(Hit(_step_beat(step), KIT_RIDE, 1.00))
    return tuple(hits)


def _motown_pattern() -> tuple[Hit, ...]:
    hits: list[Hit] = [
        Hit(_step_beat(1), KIT_KICK, 1.00),
        Hit(_step_beat(5), KIT_KICK, 1.00),
        Hit(_step_beat(8), KIT_KICK, 1.00),
        Hit(_step_beat(9), KIT_KICK, 1.00),
        Hit(_step_beat(13), KIT_KICK, 1.00),
        Hit(_step_beat(5), KIT_SNARE, 1.00),
        Hit(_step_beat(13), KIT_SNARE, 1.00),
        Hit(_step_beat(16), KIT_HAT_OPEN, 1.00),
    ]
    for step in (1, 3, 5, 7, 9, 11, 13, 15):
        hits.append(Hit(_step_beat(step), KIT_HAT_CLOSED, 1.00))
    return tuple(hits)


SEQUENCER_PATTERNS: dict[str, tuple[Hit, ...]] = {
    STYLE_JAZZ: _jazz_pattern(),
    STYLE_FUNK: _funk_pattern(),
    STYLE_ROCK: _rock_pattern(),
    STYLE_FUSION: _fusion_pattern(),
    STYLE_MOTOWN: _motown_pattern(),
}


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            return Path(bundle)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _app_icon() -> QIcon:
    icon = QIcon()
    root = _app_dir()
    ico = root / "app_icon.ico"
    png = root / "logo.png"
    packaging = root / "packaging" / "icons" / "icon_256.png"
    if ico.is_file():
        icon.addFile(str(ico))
    if png.is_file():
        icon.addFile(str(png))
    if packaging.is_file():
        icon.addFile(str(packaging))
    return icon


def _writable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


WOOD_DIR = _writable_root() / "assets" / "woods"
WOOD_FILES = {
    "ash": "buckeye_backdrop.jpg",
    "buckeye": "buckeye_backdrop.jpg",
    "zebrano": "zebrano_top.jpg",
    "redwood_burl": "redwood_left.jpg",
    "eye_poplar": "poplar_center.jpg",
    "spalted_maple": "spalted_right.jpg",
    "macassar": "spalted_right.jpg",
    "analyzer": "rosewood.jpg",
}
WOOD_FINISH = {
    "ash": {"contrast": 1.18, "color": 0.96, "vignette": 0.98, "polish": 0.08, "gloss": True, "tint": "#52463e", "amount": 0.10},
    "buckeye": {"contrast": 1.18, "color": 0.96, "vignette": 0.98, "polish": 0.08, "gloss": True, "tint": "#52463e", "amount": 0.10},
    "zebrano": {"contrast": 1.16, "color": 1.10, "vignette": 0.72, "polish": 0.18, "gloss": True, "tint": "#c4882a", "amount": 0.12},
    "redwood_burl": {"contrast": 1.16, "color": 1.12, "vignette": 0.86, "polish": 0.16, "gloss": True, "tint": "#6b2a16", "amount": 0.08},
    "eye_poplar": {"contrast": 1.14, "color": 1.04, "vignette": 0.88, "polish": 0.10, "gloss": True, "tint": "#8a6a3a", "amount": 0.06},
    "spalted_maple": {"contrast": 1.22, "color": 1.00, "vignette": 0.86, "polish": 0.12, "gloss": True, "tint": "#3a2a18", "amount": 0.08},
    "macassar": {"contrast": 1.08, "color": 1.00, "vignette": 0.70, "polish": 0.06, "gloss": True, "tint": "#ffffff", "amount": 0.00},
    "analyzer": {"contrast": 1.18, "color": 0.94, "vignette": 0.86, "polish": 0.05, "gloss": True, "tint": "#120c0a", "amount": 0.18, "brightness": 0.82, "edge": 1.22, "floor": 0.32},
}


def _hex_rgb(hex_color: str) -> np.ndarray:
    value = hex_color.lstrip("#")
    return np.array([int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)], dtype=np.float32)


def _wood_to_pixmap(rgb: np.ndarray, contrast: float, color: float, brightness: float = 1.0) -> QPixmap:
    from PIL import Image, ImageEnhance

    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    image = ImageEnhance.Contrast(image).enhance(contrast)
    image = ImageEnhance.Color(image).enhance(color)
    if abs(brightness - 1.0) > 0.001:
        image = ImageEnhance.Brightness(image).enhance(brightness)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    pix = QPixmap()
    pix.loadFromData(buf.getvalue(), "PNG")
    return pix


def _analog_vignette(width: int, height: int, strength: float, floor: float = 0.62) -> np.ndarray:
    xx, yy = np.meshgrid(
        np.linspace(-1.0, 1.0, width, dtype=np.float32),
        np.linspace(-1.0, 1.0, height, dtype=np.float32),
    )
    radial = np.sqrt(xx * xx * 0.90 + yy * yy)
    return np.clip(np.exp(-strength * np.power(np.maximum(radial - 0.22, 0.0), 1.85)), floor, 1.0)


def _satin_vignette(width: int, height: int, strength: float = 0.96) -> tuple[np.ndarray, np.ndarray]:
    xx, yy = np.meshgrid(
        np.linspace(-1.0, 1.0, width, dtype=np.float32),
        np.linspace(-1.0, 1.0, height, dtype=np.float32),
    )
    vignette = np.clip(1.18 - strength * (xx * xx * 0.78 + yy * yy), 0.18, 1.0)
    gloss = np.clip(1.0 + 0.38 * np.exp(-((xx * 0.48 + yy * 0.86 + 0.04) ** 2) / 0.18), 0.76, 1.42)
    satin = 1.0 + 0.03 * np.sin(xx * 11.0 + yy * 3.2)
    return vignette, gloss * satin


def _high_gloss_clear_coat(rgb: np.ndarray) -> np.ndarray:
    rows, cols = rgb.shape[:2]
    yy, xx = np.indices((rows, cols), dtype=np.float32)
    xn = xx / max(cols - 1, 1)
    yn = yy / max(rows - 1, 1)
    dx = (xn - 0.5) * 2.0
    dy = (yn - 0.5) * 2.0
    radial = np.sqrt(dx * dx * 0.88 + dy * dy)
    body_vignette = np.clip(1.16 - 0.86 * np.power(radial, 1.55), 0.24, 1.0)
    stripe = xn * 0.70 + yn * 0.95
    bloom_a = np.exp(-((stripe - 0.34) ** 2) / 0.016)
    bloom_b = np.exp(-((stripe - 0.58) ** 2) / 0.008)
    corner = np.exp(-((xn - 0.16) ** 2 + (yn - 0.10) ** 2) / 0.055)
    sheen = 0.34 * bloom_a + 0.22 * bloom_b + 0.12 * corner
    coated = rgb.astype(np.float32) * body_vignette[..., None]
    coated = coated + (255.0 - coated) * (sheen[..., None] * 0.62)
    coated = coated + 42.0 * bloom_a[..., None] + 22.0 * bloom_b[..., None]
    return np.clip(coated, 0, 255)


def _warm_polish(rgb: np.ndarray, amount: float) -> np.ndarray:
    if amount <= 0.0:
        return rgb
    rows, cols = rgb.shape[:2]
    yy, xx = np.indices((rows, cols), dtype=np.float32)
    xn = xx / max(cols - 1, 1)
    yn = yy / max(rows - 1, 1)
    stripe = np.exp(-((xn * 0.62 + yn * 0.88 - 0.46) ** 2) / 0.28)
    amber = np.array([184.0, 118.0, 52.0], dtype=np.float32)
    sheen = (stripe * amount)[..., None]
    coated = rgb + (amber - rgb) * sheen * 0.12
    return np.clip(coated, 0, 255)


def _colorize_grain(rgb: np.ndarray, tint_hex: str, amount: float) -> np.ndarray:
    multiply = np.clip(rgb * (_hex_rgb(tint_hex) / 255.0), 0, 255)
    return np.clip(rgb * (1.0 - amount) + multiply * amount, 0, 255)


def _finish_wood_rgb(rgb: np.ndarray, finish: dict) -> QPixmap:
    from PIL import Image, ImageEnhance

    rgb = _colorize_grain(rgb, finish.get("tint", "#ffffff"), finish.get("amount", 0.0))
    rows, cols = rgb.shape[:2]
    vignette, lacquer = _satin_vignette(cols, rows, finish["vignette"])
    rgb = rgb * vignette[..., None] * lacquer[..., None]
    rgb = rgb * _analog_vignette(cols, rows, finish.get("edge", 1.18), finish.get("floor", 0.42))[..., None]
    if finish.get("gloss", True):
        rgb = _high_gloss_clear_coat(rgb)
    rgb = _warm_polish(rgb, finish.get("polish", 0.1))
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    image = ImageEnhance.Contrast(image).enhance(finish["contrast"])
    image = ImageEnhance.Color(image).enhance(finish["color"])
    image = ImageEnhance.Brightness(image).enhance(finish.get("brightness", 1.03))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    pix = QPixmap()
    pix.loadFromData(buf.getvalue(), "PNG")
    return pix


def _photo_to_pixmap(path: Path, finish: dict) -> QPixmap:
    from PIL import Image

    image = Image.open(path).convert("RGB")
    if max(image.size) > 2048:
        image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    rgb = np.asarray(image, dtype=np.float32)
    return _finish_wood_rgb(rgb, finish)


def _wood_is_ready(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 8000
    except OSError:
        return False


def _bundled_woods_dir() -> Path:
    return _app_dir() / "assets" / "woods"


def ensure_wood_assets() -> Path:
    try:
        WOOD_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return _bundled_woods_dir()
    needed = sorted(set(WOOD_FILES.values()))
    bundled = _bundled_woods_dir()
    for name in needed:
        dest = WOOD_DIR / name
        if _wood_is_ready(dest):
            continue
        src = bundled / name
        if _wood_is_ready(src):
            if src.resolve() != dest.resolve():
                try:
                    dest.write_bytes(src.read_bytes())
                except OSError:
                    pass
    missing = [name for name in needed if not _wood_is_ready(WOOD_DIR / name) and not _wood_is_ready(bundled / name)]
    if not missing:
        return WOOD_DIR
    from woods_pack import PACK_B85

    blob = io.BytesIO(base64.b85decode(PACK_B85))
    with zipfile.ZipFile(blob) as payload:
        packed = set(payload.namelist())
        for name in missing:
            if name not in packed:
                continue
            try:
                (WOOD_DIR / name).write_bytes(payload.read(name))
            except OSError:
                continue
    return WOOD_DIR


def _wood_photo_path(filename: str) -> Path:
    local = WOOD_DIR / filename
    if _wood_is_ready(local):
        return local
    bundled = _bundled_woods_dir() / filename
    if _wood_is_ready(bundled):
        return bundled
    return local


def make_boutique_woods() -> dict[str, QPixmap]:
    ensure_wood_assets()
    woods: dict[str, QPixmap] = {}
    missing: list[str] = []
    loaded: dict[str, QPixmap] = {}
    for key, filename in WOOD_FILES.items():
        path = _wood_photo_path(filename)
        if filename not in loaded:
            if not path.is_file():
                missing.append(str(path))
                continue
            loaded[filename] = _photo_to_pixmap(path, WOOD_FINISH[key])
        woods[key] = loaded[filename]
    if missing:
        raise FileNotFoundError("Embedded wood photographs failed to extract: " + ", ".join(missing))
    return woods


def _upsample_noise(height: int, width: int, cell: int, rng: np.random.Generator) -> np.ndarray:
    gh = max(2, height // max(cell, 1) + 2)
    gw = max(2, width // max(cell, 1) + 2)
    grid = rng.random((gh, gw)).astype(np.float32)
    ys = np.linspace(0, gh - 1.001, height, dtype=np.float32)
    xs = np.linspace(0, gw - 1.001, width, dtype=np.float32)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    y1 = np.clip(y0 + 1, 0, gh - 1)
    x1 = np.clip(x0 + 1, 0, gw - 1)
    n00 = grid[y0[:, None], x0[None, :]]
    n10 = grid[y1[:, None], x0[None, :]]
    n01 = grid[y0[:, None], x1[None, :]]
    n11 = grid[y1[:, None], x1[None, :]]
    return (n00 * (1.0 - fy) + n10 * fy) * (1.0 - fx) + (n01 * (1.0 - fy) + n11 * fy) * fx


def _synth_wood_rgb(kind: str, size: tuple[int, int] | None = None) -> np.ndarray:
    specs = {
        "ash": (1280, 800, (176, 136, 94), (86, 54, 32), (236, 214, 176), 36.0, 6.4, 11, False, False),
        "buckeye": (1280, 800, (176, 136, 94), (86, 54, 32), (236, 214, 176), 36.0, 6.4, 11, False, False),
        "zebrano": (960, 640, (168, 118, 58), (48, 28, 14), (232, 196, 118), 22.0, 3.2, 22, False, True),
        "redwood_burl": (720, 960, (98, 32, 24), (40, 10, 8), (176, 78, 52), 48.0, 10.5, 33, True, False),
        "eye_poplar": (720, 960, (188, 172, 122), (96, 88, 50), (236, 224, 180), 26.0, 5.0, 44, False, False),
        "spalted_maple": (720, 960, (198, 168, 118), (46, 30, 16), (242, 226, 190), 40.0, 4.2, 55, False, True),
        "macassar": (720, 960, (28, 20, 16), (8, 6, 5), (78, 52, 36), 18.0, 2.4, 66, False, True),
        "analyzer": (1400, 520, (64, 30, 22), (16, 8, 6), (132, 70, 44), 58.0, 3.4, 77, False, False),
    }
    width, height, base, dark, light, freq, warp, seed, burl, veins = specs.get(kind, specs["ash"])
    if size is not None:
        width, height = size
    rng = np.random.default_rng(seed)
    yy, xx = np.indices((height, width), dtype=np.float32)
    xn = xx / max(width - 1, 1)
    yn = yy / max(height - 1, 1)
    n1 = _upsample_noise(height, width, 28, rng)
    n2 = _upsample_noise(height, width, 9, rng)
    n3 = _upsample_noise(height, width, 4, rng)
    field = yn * freq + warp * (n1 - 0.5) + 1.8 * np.sin((xn + n2 * 0.35) * 6.4)
    grain = 0.5 + 0.5 * np.sin(field * (2.0 * np.pi))
    grain = np.clip(np.power(np.clip(grain, 0.0, 1.0), 1.28) + (n3 - 0.5) * 0.10, 0.0, 1.0)
    if burl:
        rings = np.zeros((height, width), dtype=np.float32)
        for _ in range(16):
            cx = rng.uniform(0.0, float(width))
            cy = rng.uniform(0.0, float(height))
            rad = rng.uniform(26.0, 88.0)
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            rings += np.exp(-((dist / rad) ** 2)) * (0.5 + 0.5 * np.sin(dist / 4.2))
        grain = np.clip(grain * 0.70 + rings * 0.48, 0.0, 1.0)
    if veins:
        ink = np.clip((n1 * 0.55 + n2 * 0.45) ** 3.4, 0.0, 1.0)
        grain = np.clip(grain * (1.0 - ink * 0.72), 0.0, 1.0)
    base_c = np.array(base, dtype=np.float32)
    dark_c = np.array(dark, dtype=np.float32)
    light_c = np.array(light, dtype=np.float32)
    rgb = dark_c + (light_c - dark_c) * grain[..., None]
    rgb = rgb * 0.82 + base_c * 0.18
    pore = (rng.random((height, width, 1)).astype(np.float32) - 0.5) * 10.0
    return np.clip(rgb + pore, 0, 255)


_GENERATED_WOODS: dict[str, QPixmap] | None = None


def make_generated_woods() -> dict[str, QPixmap]:
    global _GENERATED_WOODS
    if _GENERATED_WOODS is not None:
        return _GENERATED_WOODS
    woods: dict[str, QPixmap] = {}
    cache: dict[str, QPixmap] = {}
    for key in WOOD_FILES:
        if key not in cache:
            cache[key] = _finish_wood_rgb(_synth_wood_rgb(key), WOOD_FINISH[key])
        woods[key] = cache[key]
    # ash and buckeye share a look; keep identical pixmap if already generated
    woods["buckeye"] = woods["ash"]
    _GENERATED_WOODS = woods
    return woods


def _prefs() -> QSettings:
    return QSettings("AntonShcherbakov", "GrooveTrainer")


def load_prefs() -> tuple[str, str]:
    store = _prefs()
    lang = str(store.value("lang", ""))
    skin = str(store.value("skin", "photo"))
    if lang not in UI_STRINGS:
        lang = "ru" if QLocale.system().language() == QLocale.Language.Russian else "en"
    if skin not in {"photo", "generated"}:
        skin = "photo"
    return lang, skin


def save_prefs() -> None:
    store = _prefs()
    store.setValue("lang", APP_LANG)
    store.setValue("skin", APP_SKIN)


def _fade(samples: np.ndarray, fade_samples: int = 64) -> np.ndarray:
    if len(samples) < fade_samples * 2:
        return samples
    samples[:fade_samples] *= np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
    samples[-fade_samples:] *= np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
    return samples


def _stereo(signal: np.ndarray) -> np.ndarray:
    clipped = np.clip(signal.astype(np.float32), -1.0, 1.0)
    return np.column_stack((clipped, clipped))


def synth_click(freq: float, duration_s: float = 0.016, accent: float = 1.0) -> np.ndarray:
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    tone = np.sin(2.0 * np.pi * freq * t)
    overtone = 0.32 * np.sin(2.0 * np.pi * freq * 2.4 * t)
    env = np.exp(-40.0 * t).astype(np.float32)
    click = (tone + overtone) * env * accent
    return _stereo(_fade(click, 48))


def synth_kick(duration_s: float = 0.18) -> np.ndarray:
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    freq_env = 120.0 * np.exp(-26.0 * t) + 38.0
    phase = 2.0 * np.pi * np.cumsum(freq_env) / SAMPLE_RATE
    body = np.sin(phase)
    punch = 0.2 * np.sin(2.0 * phase)
    attack = (
        0.1
        * np.random.default_rng(1).uniform(-1.0, 1.0, n).astype(np.float32)
        * np.exp(-80.0 * t)
    )
    env = np.exp(-10.0 * t).astype(np.float32)
    kick = (body + punch) * env + attack
    return _stereo(_fade(0.95 * kick, 48))


def synth_snare(duration_s: float = 0.13) -> np.ndarray:
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    rng = np.random.default_rng(2)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    tone = 0.25 * np.sin(2.0 * np.pi * 180.0 * t) + 0.12 * np.sin(2.0 * np.pi * 330.0 * t)
    env_noise = np.exp(-28.0 * t).astype(np.float32)
    env_tone = np.exp(-18.0 * t).astype(np.float32)
    snare = 0.78 * noise * env_noise + tone * env_tone
    return _stereo(_fade(0.85 * snare, 48))


def synth_hihat(duration_s: float = 0.045) -> np.ndarray:
    n = int(SAMPLE_RATE * duration_s)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    rng = np.random.default_rng(3)
    noise = rng.uniform(-1.0, 1.0, n).astype(np.float32)
    bright = noise - 0.65 * np.roll(noise, 1)
    env = np.exp(-85.0 * t).astype(np.float32)
    hat = 0.55 * bright * env
    return _stereo(_fade(hat, 32))


def make_drum_kit() -> dict[str, np.ndarray]:
    kick = synth_kick(0.18)
    snare = synth_snare(0.13)
    hihat = synth_hihat(0.045)
    return {
        KIT_KICK: kick,
        KIT_SNARE: snare,
        KIT_HAT_CLOSED: hihat,
        KIT_HAT_OPEN: hihat,
        KIT_RIDE: hihat,
    }


def _voice_gain(sound: str, velocity: float, drum_vol: float) -> float:
    gain = velocity * drum_vol
    if sound in {KIT_HAT_CLOSED, KIT_HAT_OPEN, KIT_RIDE}:
        gain *= 0.82
    return gain


def _beat_index(beat: float, bar_samples: int) -> int:
    return int(round((beat / 4.0) * bar_samples)) % max(1, bar_samples)


def _hit_start_in_bar(hit: Hit, style: str, bar_samples: int) -> int:
    return _beat_index(hit.beat, bar_samples)


@dataclass(frozen=True, order=True)
class VoiceEvent:
    abs_sample: int
    order: int
    sound: str
    gain: float
    choke_open: bool = False


class _Signals(QObject):
    beat_flash = pyqtSignal(int)


_signals = _Signals()


@dataclass(frozen=True)
class MetroEvent:
    sample_index: int
    gain: float
    step: int


class DrumVoice:
    CHOKABLE = {KIT_HAT_OPEN}

    def __init__(self, sound: str, buf: np.ndarray, start_abs: int, gain: float):
        self.sound = sound
        self.buf = buf * np.float32(gain)
        self.start_abs = start_abs
        self.playhead = 0
        self.choke_abs: int | None = None
        self.done = False

    def choke_at(self, abs_sample: int) -> None:
        if self.sound not in self.CHOKABLE:
            return
        if self.choke_abs is None or abs_sample < self.choke_abs:
            self.choke_abs = abs_sample

    def mix(self, out: np.ndarray, block_start: int) -> None:
        if self.done or self.buf.size == 0:
            self.done = True
            return
        frames = len(out)
        rel_start = self.start_abs - block_start
        if rel_start >= frames:
            return
        pos = max(0, rel_start)
        src = self.playhead
        length = min(frames - pos, len(self.buf) - src)
        if self.choke_abs is not None:
            choke_rel = self.choke_abs - block_start
            if choke_rel <= pos:
                self.done = True
                return
            fade_end = choke_rel + CHOKE_FADE
            if pos >= fade_end:
                self.done = True
                return
            length = min(length, fade_end - pos)
        if length <= 0:
            if src >= len(self.buf):
                self.done = True
            return
        chunk = self.buf[src : src + length]
        if self.choke_abs is not None:
            abs_idx = (np.arange(length, dtype=np.int32) + block_start + pos).astype(np.float32)
            fade = np.clip(1.0 - (abs_idx - self.choke_abs) / CHOKE_FADE, 0.0, 1.0)
            chunk = chunk * fade[:, None]
        out[pos : pos + length] += chunk
        self.playhead = src + length
        reached_end = self.playhead >= len(self.buf)
        fade_done = (
            self.choke_abs is not None
            and (block_start + pos + length) >= self.choke_abs + CHOKE_FADE
        )
        if reached_end or fade_done:
            self.done = True


class AudioEngine:
    def __init__(self, kit: dict[str, np.ndarray]):
        self.kit = kit
        self.bpm = 100
        self.running = False
        self.drum_vol = 0.8
        self.metro_vol = 0.8
        self.metro_freq = 1000.0
        self.micro_offset_ms = 0
        self.metronome_subdivision = SUBDIVISION_QUARTERS
        self.style = STYLE_JAZZ
        self._lock = threading.Lock()
        self._stream: sd.OutputStream | None = None
        self._timeline_sample = 0
        self._last_led_step = -1
        self._event_counter = 0
        self._voices: list[DrumVoice] = []

    def set_style(self, style: str):
        with self._lock:
            self.style = style
            self._voices.clear()

    def set_bpm(self, bpm: int):
        with self._lock:
            self.bpm = int(bpm)

    def start(self):
        if self.running:
            return
        self.running = True
        self._timeline_sample = 0
        self._last_led_step = -1
        with self._lock:
            self._voices.clear()
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=BLOCKSIZE,
            latency="low",
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self):
        self.running = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            self._voices.clear()

    def shutdown(self):
        self.stop()

    def _snapshot(self):
        with self._lock:
            return {
                "bpm": self.bpm,
                "drum_vol": self.drum_vol,
                "metro_vol": self.metro_vol,
                "metro_freq": self.metro_freq,
                "micro_offset_ms": self.micro_offset_ms,
                "metronome_subdivision": self.metronome_subdivision,
                "style": self.style,
            }

    def _next_order(self) -> int:
        self._event_counter += 1
        return self._event_counter

    def _collect_voice_events(
        self,
        start_sample: int,
        end_sample: int,
        bar_samples: int,
        style: str,
        drum_vol: float,
    ) -> list[VoiceEvent]:
        pattern = SEQUENCER_PATTERNS[style]
        first_bar = start_sample // bar_samples - 1
        last_bar = end_sample // bar_samples + 1
        events: list[VoiceEvent] = []
        for bar in range(first_bar, last_bar + 1):
            bar_start = bar * bar_samples
            for hit in pattern:
                if hit.velocity <= 0 or hit.sound not in self.kit:
                    continue
                abs_t = bar_start + _hit_start_in_bar(hit, style, bar_samples)
                if not (start_sample <= abs_t < end_sample):
                    continue
                events.append(
                    VoiceEvent(
                        abs_t,
                        self._next_order(),
                        hit.sound,
                        _voice_gain(hit.sound, hit.velocity, drum_vol),
                        choke_open=False,
                    )
                )
        events.sort()
        return events

    def _spawn_voices(self, events: list[VoiceEvent]) -> None:
        for event in events:
            if event.choke_open:
                for voice in self._voices:
                    if voice.sound == KIT_HAT_OPEN and not voice.done:
                        voice.choke_at(event.abs_sample)
            buf = self.kit.get(event.sound)
            if buf is None or buf.size == 0:
                continue
            self._voices.append(DrumVoice(event.sound, buf, event.abs_sample, event.gain))

    def _mix_voices(self, out: np.ndarray, block_start: int) -> None:
        alive: list[DrumVoice] = []
        for voice in self._voices:
            voice.mix(out, block_start)
            if not voice.done:
                alive.append(voice)
        self._voices = alive

    def _audio_callback(self, outdata, frames, time_info, status):
        state = self._snapshot()
        bpm = max(40, min(240, state["bpm"]))
        bar_samples = max(1, int(round(4.0 * 60.0 / bpm * SAMPLE_RATE)))
        eighth_samples = max(1, bar_samples // PATTERN_LEN)
        start_sample = self._timeline_sample
        end_sample = start_sample + frames
        out = np.zeros((frames, CHANNELS), dtype=np.float32)
        with self._lock:
            events = self._collect_voice_events(
                start_sample, end_sample, bar_samples, state["style"], state["drum_vol"]
            )
            self._spawn_voices(events)
            self._mix_voices(out, start_sample)
        for event in self._collect_metro(
            start_sample, end_sample, bar_samples, eighth_samples, state
        ):
            click = synth_click(state["metro_freq"], accent=event.gain)
            self._mix_buffer(out, start_sample, click, event.sample_index)
        np.clip(out, -1.0, 1.0, out=out)
        outdata[:] = out
        self._timeline_sample = end_sample

    def _mix_buffer(self, out: np.ndarray, block_start: int, buf: np.ndarray, play_start_abs: int) -> None:
        dest = play_start_abs - block_start
        src = 0
        if dest < 0:
            src -= dest
            dest = 0
        if src >= len(buf) or dest >= len(out):
            return
        length = min(len(out) - dest, len(buf) - src)
        if length <= 0:
            return
        out[dest : dest + length] += buf[src : src + length]

    def _collect_metro(
        self,
        start_sample: int,
        end_sample: int,
        bar_samples: int,
        eighth_samples: int,
        state: dict,
    ) -> list[MetroEvent]:
        events: list[MetroEvent] = []
        lookback = int(round(0.060 * SAMPLE_RATE)) + abs(
            int(round((state["micro_offset_ms"] / 1000.0) * SAMPLE_RATE))
        )
        first_bar = (start_sample - lookback) // bar_samples - 1
        last_bar = end_sample // bar_samples + 1
        for bar in range(first_bar, last_bar + 1):
            bar_start = bar * bar_samples
            for eighth in range(PATTERN_LEN):
                grid_sample = bar_start + eighth * eighth_samples
                if start_sample <= grid_sample < end_sample and eighth != self._last_led_step:
                    _signals.beat_flash.emit(eighth)
                    self._last_led_step = eighth
                if _should_emit_metronome(eighth, state["metronome_subdivision"]):
                    metro_sample = grid_sample - int(
                        round((state["micro_offset_ms"] / 1000.0) * SAMPLE_RATE)
                    )
                    accent = 1.0 if eighth == 0 else 0.72
                    events.append(MetroEvent(metro_sample, state["metro_vol"] * accent, eighth))
        return events


def _should_emit_metronome(step_index: int, subdivision: str) -> bool:
    if subdivision == SUBDIVISION_EIGHTHS:
        return True
    return step_index in {0, 2, 4, 6}

DARK_STYLE = f"""
QMainWindow {{ background-color: {THEME_INK}; color: #ffffff; font-family: "Segoe UI", sans-serif; }}
QWidget {{ color: #ffffff; font-family: "Segoe UI", sans-serif; }}
QWidget#coverRoot {{ background: transparent; }}
QFrame#card, QFrame#innerCard {{
    background-color: rgba(10, 9, 8, 188);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 10px;
}}
QFrame#presetBlock {{
    background: transparent;
    border: none;
}}
QFrame#innerCard {{ background-color: rgba(8, 7, 6, 198); }}
QFrame#analyzerCard {{
    background: transparent;
    border: none;
}}
QFrame#analyzerPlate {{
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 183, 3, 0.55);
    border-radius: 12px;
}}
QLabel#headerHint {{
    color: #f8f9fa;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.35px;
    margin-left: 22px;
    margin-top: 2px;
    margin-right: 12px;
    padding: 0px;
    background: transparent;
    border: none;
}}
QPushButton#chromeChip {{
    background-color: rgba(8, 6, 5, 168);
    color: #f6f1e8;
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 8px;
    padding: 4px 8px;
    min-height: 28px;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.6px;
}}
QPushButton#chromeChip:hover {{
    border-color: rgba(255, 183, 3, 0.55);
}}
QPushButton#chromeChip:checked {{
    background-color: rgba(0, 229, 255, 0.16);
    border: 1px solid rgba(0, 229, 255, 0.88);
    color: #ffffff;
}}
QWidget#chromeBar {{
    background: transparent;
}}
QLabel#analyzerKicker {{ color: {THEME_GOLD}; font-size: 11px; font-weight: 800; letter-spacing: 2.4px; }}
QLabel#analyzerName {{ color: #ffffff; font-size: 30px; font-weight: 900; letter-spacing: 0.3px; }}
QLabel#analyzerGenre {{ color: #f5f5f5; font-size: 14px; font-weight: 700; letter-spacing: 1.0px; }}
QLabel#analyzerMeta {{ color: {THEME_GOLD}; font-size: 13px; font-weight: 800; }}
QLabel#analyzerBio {{ color: #e8e2da; font-size: 20px; line-height: 1.5; font-family: "Sitka Text", Georgia, "Segoe UI"; }}
QLabel#cardHeader {{
    font-size: 11px; font-weight: 800; color: {THEME_GOLD_SOFT};
    letter-spacing: 1.6px; text-transform: uppercase;
}}
QLabel#valueLabel, QLabel#hintLabel {{ color: #b8b0a6; }}
QLabel#sectionLabel {{ color: #ffffff; font-weight: 700; letter-spacing: 0.8px; }}
QLabel#presetTitle {{
    color: #f6f1e8;
    font-size: 15px;
    font-weight: 600;
    background: transparent;
}}
QLabel#presetSub {{
    color: #ffd27a;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}}
QLabel#pocketHeading {{
    color: #ffe7a8;
    font-size: 14px;
    font-weight: 600;
    background: transparent;
}}
QLabel#grooveCopy {{
    color: #f0eadf;
    background: transparent;
}}
QFrame#readPlate {{
    background: transparent;
    border: none;
}}
QTabWidget::pane {{
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    background: rgba(8, 6, 5, 108);
    top: -1px;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: rgba(14, 12, 10, 160);
    color: #d8d2ca;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-bottom: 2px solid transparent;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 12px 32px 10px 32px;
    margin-right: 6px;
    min-width: 108px;
    font-weight: 800;
    font-size: 13px;
    letter-spacing: 1.5px;
}}
QTabBar::tab:selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(18, 16, 22, 210),
        stop:0.45 rgba(10, 10, 14, 180),
        stop:1 rgba(8, 7, 6, 120));
    color: transparent;
    border: 1px solid rgba(0, 229, 255, 0.88);
    border-bottom: 2px solid rgba(0, 229, 255, 0.95);
}}
QTabBar::tab:hover:!selected {{
    background: rgba(255, 255, 255, 0.06);
    color: #ffffff;
    border-color: rgba(255, 183, 3, 0.22);
}}
QSlider::groove:horizontal {{
    height: 9px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 5px;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(0, 229, 255, 40), stop:1 rgba(0, 229, 255, 90));
    border-radius: 5px;
}}
QSlider::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {THEME_CYAN_SOFT}, stop:1 {THEME_CYAN});
    border: 1px solid #ffffff;
    width: 17px; height: 17px;
    margin: -5px 0; border-radius: 9px;
}}
QPushButton {{
    background-color: rgba(16, 14, 12, 220);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 12px; color: #ffffff;
}}
QPushButton:hover {{
    background-color: rgba(24, 20, 16, 235);
    border-color: rgba(255, 183, 3, 0.28);
}}
QPushButton#startBtn {{
    font-size: 16px; font-weight: 900; padding: 11px 20px; border-radius: 11px;
    letter-spacing: 0.6px;
}}
QPushButton#startBtn[playing="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(0, 229, 255, 28), stop:1 rgba(8, 10, 12, 230));
    border: 1px solid {THEME_CYAN};
    color: #ffffff;
}}
QPushButton#startBtn[playing="false"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(32, 22, 14, 240), stop:1 rgba(14, 10, 8, 230));
    border: 1px solid rgba(255, 183, 3, 0.35);
    color: #ffffff;
}}
QPushButton#presetTile {{
    background-color: transparent;
    color: #f6f1e8;
    border-radius: 11px;
    padding: 0px;
    min-width: 140px;
    min-height: 96px;
    max-height: 96px;
    border: none;
}}
QPushButton#presetTile:hover:!checked {{
    background-color: transparent;
}}
QPushButton#presetTile:checked,
QPushButton#presetTile[presetActive="true"] {{
    background: transparent;
    border: none;
    padding-top: 2px;
    padding-left: 1px;
}}
QPushButton#presetTile:pressed {{
    padding-top: 2px;
    padding-left: 1px;
    background: transparent;
}}
QComboBox, QSpinBox {{
    background-color: rgba(14, 12, 10, 220);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 4px 8px; color: #ffffff;
}}
QComboBox:hover, QSpinBox:hover {{
    border-color: rgba(255, 183, 3, 0.22);
}}
QComboBox QAbstractItemView {{
    background-color: #12100e;
    color: #ffffff;
    selection-background-color: rgba(0, 229, 255, 36);
    border: 1px solid rgba(255, 255, 255, 0.08);
}}
QSpinBox#bpmSpin {{
    font-size: 24px; font-weight: 900; padding: 2px 8px;
    color: {THEME_GOLD};
}}
QScrollArea {{ border: none; background: transparent; }}
"""


def _reading_font(pixel_size: int) -> QFont:
    font = QFont()
    font.setFamilies(["Sitka Text", "Georgia", "Cambria", "Calibri", "Segoe UI"])
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


def _legible_label(label: QLabel, *, color: str = "#ffffff", glow: str = "#000000") -> None:
    shadow = QGraphicsDropShadowEffect(label)
    shadow.setBlurRadius(10)
    shadow.setOffset(0, 1)
    shadow.setColor(QColor(glow))
    label.setGraphicsEffect(shadow)
    font = label.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    label.setFont(font)
    palette = label.palette()
    qcolor = QColor(color)
    palette.setColor(QPalette.ColorRole.WindowText, qcolor)
    palette.setColor(QPalette.ColorRole.Text, qcolor)
    label.setPalette(palette)
    label.setStyleSheet(f"color: {color}; background: transparent;")


def _elevate(
    widget: QWidget,
    *,
    blur: int = 28,
    y: int = 4,
    alpha: int = 140,
    color: QColor | None = None,
) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y)
    shadow.setColor(color if color is not None else QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)


def _paint_gold_glass(painter: QPainter, rect: QRectF, *, selected: bool = True, radius: float = 10.0) -> None:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setClipPath(path)
    painter.fillPath(path, QColor(8, 6, 5, 148 if selected else 176))
    glass = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    if selected:
        glass.setColorAt(0.00, QColor(255, 255, 255, 40))
        glass.setColorAt(0.14, QColor(255, 183, 3, 36))
        glass.setColorAt(0.38, QColor(255, 255, 255, 12))
        glass.setColorAt(1.00, QColor(255, 183, 3, 10))
    else:
        glass.setColorAt(0.00, QColor(255, 255, 255, 16))
        glass.setColorAt(0.45, QColor(255, 255, 255, 6))
        glass.setColorAt(1.00, QColor(255, 255, 255, 0))
    painter.fillPath(path, glass)
    spec = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + min(26.0, rect.height() * 0.35)))
    spec.setColorAt(0.00, QColor(255, 255, 255, 96 if selected else 36))
    spec.setColorAt(0.55, QColor(255, 255, 255, 18 if selected else 8))
    spec.setColorAt(1.00, QColor(255, 255, 255, 0))
    painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), min(26.0, rect.height() * 0.35)), spec)
    if selected:
        glow = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.62)
        glow.setColorAt(0.00, QColor(255, 183, 3, 38))
        glow.setColorAt(0.55, QColor(255, 183, 3, 10))
        glow.setColorAt(1.00, QColor(255, 183, 3, 0))
        painter.fillPath(path, glow)
    painter.setClipping(False)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if selected:
        painter.setPen(QPen(QColor(255, 183, 3, 217), 1.15))
        painter.drawRoundedRect(rect, radius, radius)
        painter.setPen(QPen(QColor(255, 236, 170, 78), 1.0))
        painter.drawRoundedRect(rect.adjusted(2.2, 2.2, -2.2, -2.2), max(6.0, radius - 1.6), max(6.0, radius - 1.6))
    else:
        painter.setPen(QPen(QColor(255, 255, 255, 36), 1.0))
        painter.drawRoundedRect(rect, radius, radius)
    painter.restore()


def _paint_star_letters(painter: QPainter, rect: QRectF, text: str, font: QFont) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    metrics = QFontMetricsF(font)
    bounds = metrics.tightBoundingRect(text)
    x = rect.x() + (rect.width() - bounds.width()) / 2.0 - bounds.x()
    y = rect.y() + (rect.height() + metrics.ascent() - metrics.descent()) / 2.0 - 1.0
    path = QPainterPath()
    path.addText(QPointF(x, y), font, text)
    ink = QPen(QColor(8, 6, 4, 230), 7.0)
    ink.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.strokePath(path, ink)
    for width, color in (
        (9.0, QColor(255, 183, 3, 28)),
        (5.5, QColor(255, 210, 120, 55)),
        (3.0, QColor(236, 244, 255, 70)),
    ):
        pen = QPen(color, width)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, pen)
    fill = QLinearGradient(path.boundingRect().topLeft(), path.boundingRect().bottomLeft())
    fill.setColorAt(0.00, QColor(255, 252, 245))
    fill.setColorAt(0.22, QColor(255, 220, 140))
    fill.setColorAt(0.48, QColor(236, 242, 250))
    fill.setColorAt(0.78, QColor(186, 198, 214))
    fill.setColorAt(1.00, QColor(255, 183, 3))
    painter.fillPath(path, fill)
    painter.save()
    painter.setClipPath(path)
    rng = np.random.default_rng(sum((i + 3) * ord(ch) for i, ch in enumerate(text)) % (2**32))
    box = path.boundingRect().adjusted(-4.0, -6.0, 4.0, 6.0)
    star_count = max(28, int(box.width() * 0.55))
    for _ in range(star_count):
        sx = float(box.left() + rng.random() * max(box.width(), 1.0))
        sy = float(box.top() + rng.random() * max(box.height(), 1.0))
        size = 0.6 + float(rng.random()) * 1.35
        spark = 170 + int(rng.integers(0, 85))
        goldish = rng.random() > 0.62
        color = QColor(255, 220, 140, spark) if goldish else QColor(240, 246, 255, spark)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(sx, sy), size, size)
    painter.restore()
    painter.setPen(QPen(QColor(255, 255, 255, 90), 0.8))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.strokePath(path, painter.pen())


def _paint_star_paragraph(painter: QPainter, rect: QRectF, text: str, font: QFont, align: Qt.AlignmentFlag) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setFont(font)
    flags = int(align) | int(Qt.TextFlag.TextWordWrap)
    halo = QColor(8, 6, 4, 220)
    for dx, dy in (
        (-2, 0), (2, 0), (0, -2), (0, 2),
        (-1, -1), (1, -1), (-1, 1), (1, 1),
        (-1, 0), (1, 0), (0, -1), (0, 1),
    ):
        painter.setPen(halo)
        painter.drawText(rect.translated(dx, dy), flags, text)
    painter.setPen(QColor(255, 183, 3, 36))
    painter.drawText(rect.adjusted(-1.2, 0, -1.2, 0), flags, text)
    painter.drawText(rect.adjusted(1.2, 0, 1.2, 0), flags, text)
    painter.setPen(QColor(220, 232, 255, 48))
    painter.drawText(rect.adjusted(0, 1.2, 0, 1.2), flags, text)
    painter.setPen(QColor(255, 236, 196))
    painter.drawText(rect, flags, text)
    painter.save()
    painter.setClipRect(rect)
    rng = np.random.default_rng(sum((i + 5) * ord(ch) for i, ch in enumerate(text[:80])) % (2**32))
    star_count = max(18, int(rect.width() * rect.height() / 1400.0))
    for _ in range(star_count):
        sx = float(rect.left() + rng.random() * max(rect.width(), 1.0))
        sy = float(rect.top() + rng.random() * max(rect.height(), 1.0))
        size = 0.45 + float(rng.random()) * 1.05
        spark = 110 + int(rng.integers(0, 90))
        goldish = rng.random() > 0.55
        color = QColor(255, 220, 140, spark) if goldish else QColor(236, 244, 255, spark)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(sx, sy), size, size)
    painter.restore()


class StarlitLabel(QLabel):
    def __init__(self, text: str = "", *, hero: bool = False, idle_color: str = "#ffffff", parent=None):
        super().__init__(text, parent)
        self._hero = hero
        self._starlit = True
        self._idle_color = idle_color
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("color: transparent; background: transparent;")

    def set_starlit(self, active: bool) -> None:
        self._starlit = active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(self.rect()).adjusted(2.0, 1.0, -2.0, -1.0)
        text = self.text()
        if not text:
            return
        font = QFont(self.font())
        if self._hero and not self.wordWrap():
            font.setWeight(QFont.Weight.Black)
            _paint_star_letters(painter, rect, text, font)
            return
        if self._hero:
            font.setWeight(QFont.Weight.Black)
            if QFontMetricsF(font).horizontalAdvance(text) <= max(24.0, rect.width() - 8.0):
                _paint_star_letters(painter, rect, text, font)
                return
        if not self._starlit:
            painter.setFont(font)
            flags = int(self.alignment())
            if self.wordWrap():
                flags |= int(Qt.TextFlag.TextWordWrap)
            halo = QColor(8, 6, 4, 230)
            for dx, dy in (
                (-2, 0), (2, 0), (0, -2), (0, 2),
                (-1, -1), (1, -1), (-1, 1), (1, 1),
                (-1, 0), (1, 0), (0, -1), (0, 1),
            ):
                painter.setPen(halo)
                painter.drawText(rect.translated(dx, dy), flags, text)
            painter.setPen(QColor(self._idle_color))
            painter.drawText(rect, flags, text)
            return
        _paint_star_paragraph(painter, rect, text, font, self.alignment())


class GlassPlate(QFrame):
    def __init__(self, parent=None, *, dim: bool = False):
        super().__init__(parent)
        self._dim = dim
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.2, 1.2, -1.2, -1.2)
        if not self._dim:
            _paint_gold_glass(painter, rect, selected=True, radius=12.0)
            return
        path = QPainterPath()
        path.addRoundedRect(rect, 10.0, 10.0)
        painter.setClipPath(path)
        painter.fillPath(path, QColor(8, 6, 5, 172))
        glass = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        glass.setColorAt(0.00, QColor(255, 255, 255, 28))
        glass.setColorAt(0.22, QColor(255, 255, 255, 10))
        glass.setColorAt(1.00, QColor(0, 0, 0, 36))
        painter.fillPath(path, glass)
        spec = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + 16.0))
        spec.setColorAt(0.00, QColor(255, 255, 255, 42))
        spec.setColorAt(1.00, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), 16.0), spec)
        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 38), 1.0))
        painter.drawRoundedRect(rect, 10.0, 10.0)


def _flag_pixmap(kind: str) -> QPixmap:
    pix = QPixmap(28, 18)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(0, 0, 0, 80), 1.0))
    painter.setBrush(QColor(255, 255, 255))
    painter.drawRoundedRect(QRectF(0.5, 0.5, 27.0, 17.0), 2.0, 2.0)
    if kind == "us":
        stripe_h = 17.0 / 7.0
        for index in range(7):
            color = QColor(191, 10, 48) if index % 2 == 0 else QColor(255, 255, 255)
            painter.fillRect(QRectF(0.5, 0.5 + index * stripe_h, 27.0, stripe_h), color)
        painter.fillRect(QRectF(0.5, 0.5, 11.5, stripe_h * 4), QColor(10, 49, 97))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255))
        for row in range(3):
            for col in range(4):
                painter.drawEllipse(QPointF(2.2 + col * 2.6, 2.2 + row * 2.6), 0.55, 0.55)
    else:
        painter.fillRect(QRectF(0.5, 0.5, 27.0, 5.7), QColor(255, 255, 255))
        painter.fillRect(QRectF(0.5, 6.2, 27.0, 5.7), QColor(0, 57, 166))
        painter.fillRect(QRectF(0.5, 11.9, 27.0, 5.6), QColor(213, 43, 30))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 0, 0, 90), 1.0))
    painter.drawRoundedRect(QRectF(0.5, 0.5, 27.0, 17.0), 2.0, 2.0)
    painter.end()
    return pix


def _wood_swatch(wood: QPixmap) -> QIcon:
    if wood.isNull():
        return QIcon()
    scaled = wood.scaled(28, 18, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - 28) // 2)
    y = max(0, (scaled.height() - 18) // 2)
    return QIcon(scaled.copy(QRect(x, y, 28, 18)))


def _make_chrome_chip(text: str, icon: QIcon | None = None) -> QPushButton:
    chip = QPushButton(text)
    chip.setObjectName("chromeChip")
    chip.setCheckable(True)
    chip.setCursor(Qt.CursorShape.PointingHandCursor)
    chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    if icon is not None:
        chip.setIcon(icon)
        chip.setIconSize(QSize(28, 18))
    return chip


class WoodPanel(QFrame):
    WASH = {
        "behind": QColor(42, 6, 12, 36),
        "center": QColor(6, 6, 8, 44),
        "ahead": QColor(36, 20, 4, 32),
    }

    def __init__(self, wood: QPixmap, border_hex: str = "graphite", object_name: str = "woodPanel", parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self._wood = wood
        if border_hex == "graphite":
            self._border = QColor(255, 255, 255, 22)
        else:
            border = QColor(border_hex)
            border.setAlpha(96)
            self._border = border
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_wood(self, wood: QPixmap) -> None:
        self._wood = wood
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 12.0, 12.0)
        painter.setClipPath(path)
        if self._wood.isNull():
            painter.fillPath(path, QColor(24, 18, 12))
        else:
            scaled = self._wood.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        tint = self.property("tint")
        if isinstance(tint, str) and tint in self.WASH:
            painter.fillPath(path, self.WASH[tint])
        edge = min(48.0, rect.width() * 0.10, rect.height() * 0.16)
        top = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.top() + edge)
        top.setColorAt(0.0, QColor(0, 0, 0, 88))
        top.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), edge), top)
        bottom = QLinearGradient(rect.left(), rect.bottom(), rect.left(), rect.bottom() - edge)
        bottom.setColorAt(0.0, QColor(0, 0, 0, 96))
        bottom.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(rect.left(), rect.bottom() - edge, rect.width(), edge), bottom)
        if self.objectName() == "analyzerCard":
            gloss = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gloss.setColorAt(0.00, QColor(255, 183, 3, 42))
            gloss.setColorAt(0.16, QColor(255, 183, 3, 0))
            gloss.setColorAt(0.42, QColor(196, 136, 42, 28))
            gloss.setColorAt(0.56, QColor(255, 183, 3, 0))
            gloss.setColorAt(1.00, QColor(0, 0, 0, 22))
            painter.fillPath(path, gloss)
        elif self.objectName() == "presetBlock":
            gloss = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gloss.setColorAt(0.00, QColor(255, 255, 255, 48))
            gloss.setColorAt(0.14, QColor(255, 255, 255, 0))
            gloss.setColorAt(0.36, QColor(255, 255, 255, 24))
            gloss.setColorAt(0.50, QColor(255, 255, 255, 0))
            gloss.setColorAt(1.00, QColor(0, 0, 0, 18))
            painter.fillPath(path, gloss)
        painter.setClipping(False)
        painter.setPen(QPen(self._border, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.6, 0.6, -0.6, -0.6), 12.0, 12.0)
        if self.objectName() == "analyzerCard":
            halo = QPen(QColor(0, 229, 255, 28), 0.8)
            painter.setPen(halo)
            painter.drawRoundedRect(rect.adjusted(2.0, 2.0, -2.0, -2.0), 11.0, 11.0)


class CoverBackground(QWidget):
    def __init__(self, ash: QPixmap, parent=None):
        super().__init__(parent)
        self.setObjectName("coverRoot")
        self._ash = ash

    def set_ash(self, ash: QPixmap) -> None:
        self._ash = ash
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._ash.isNull():
            painter.fillRect(self.rect(), QColor(30, 20, 15))
            return
        scaled = self._ash.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        center = self.rect().center()
        warm = QRadialGradient(float(center.x()), float(center.y()), max(self.width(), self.height()) * 0.52)
        warm.setColorAt(0.00, QColor(255, 183, 3, 24))
        warm.setColorAt(0.38, QColor(255, 140, 0, 10))
        warm.setColorAt(0.72, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), warm)
        vignette = QRadialGradient(float(center.x()), float(center.y()), max(self.width(), self.height()) * 0.82)
        vignette.setColorAt(0.00, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.48, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.78, QColor(0, 0, 0, 110))
        vignette.setColorAt(1.00, QColor(0, 0, 0, 185))
        painter.fillRect(self.rect(), vignette)


class GrooveAnalyzer(WoodPanel):
    def __init__(self, wood: QPixmap, parent=None):
        super().__init__(wood, "graphite", "analyzerCard", parent)
        self.setMinimumHeight(220)
        _elevate(self, blur=44, y=6, alpha=100, color=QColor(255, 183, 3, 48))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(8)
        self.kicker = StarlitLabel(t("kicker"))
        self.kicker.setObjectName("analyzerKicker")
        self.kicker.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.kicker.setStyleSheet("color: transparent; background: transparent; font-size: 11px; font-weight: 800; letter-spacing: 2.4px;")
        plate = GlassPlate()
        plate.setObjectName("analyzerPlate")
        plate.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        plate_layout = QVBoxLayout(plate)
        plate_layout.setContentsMargins(16, 12, 16, 14)
        plate_layout.setSpacing(6)
        self.name_label = StarlitLabel(t("select_musician"), hero=True)
        self.name_label.setObjectName("analyzerName")
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.name_label.setStyleSheet(
            "color: transparent; background: transparent; font-size: 30px; font-weight: 900; letter-spacing: 0.3px;"
        )
        self.genre_label = StarlitLabel(f"{t('tab_genre')}  ·  {style_tab_label(STYLE_JAZZ)}")
        self.genre_label.setObjectName("analyzerGenre")
        self.genre_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.genre_label.setStyleSheet(
            "color: transparent; background: transparent; font-size: 14px; font-weight: 700; letter-spacing: 1.0px;"
        )
        self.meta_label = StarlitLabel(t("no_profile"))
        self.meta_label.setObjectName("analyzerMeta")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.meta_label.setStyleSheet(
            "color: transparent; background: transparent; font-size: 13px; font-weight: 800;"
        )
        self.bio_label = StarlitLabel(t("idle_bio"))
        self.bio_label.setObjectName("analyzerBio")
        self.bio_label.setWordWrap(True)
        self.bio_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.bio_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.bio_label.setFont(_reading_font(20))
        self.bio_label.setStyleSheet(
            "color: transparent; background: transparent; font-size: 20px;"
        )
        plate_layout.addWidget(self.name_label)
        plate_layout.addWidget(self.genre_label)
        plate_layout.addWidget(self.meta_label)
        plate_layout.addWidget(self.bio_label, 1)
        layout.addWidget(self.kicker)
        layout.addWidget(plate, 1)

    def retranslate(self, genre: str, active_name: str = "", pocket: str = "", offset_ms: int = 0) -> None:
        self.kicker.setText(t("kicker"))
        if active_name:
            self.show_musician(active_name, pocket, genre, offset_ms)
        else:
            self.clear_profile(genre)

    def show_musician(self, name: str, pocket: str, genre: str, offset_ms: int):
        title = anton_display() if name.startswith("Anton Shcherbakov") else name
        self.name_label.setText(title)
        self.genre_label.setText(f"{t('tab_genre')}  ·  {genre}")
        self.meta_label.setText(f"{pocket}  ·  {offset_ms:+d} ms")
        self.bio_label.setText(groove_bio(name))

    def clear_profile(self, genre: str):
        self.name_label.setText(t("select_musician"))
        self.genre_label.setText(f"{t('tab_genre')}  ·  {genre}")
        self.meta_label.setText(t("no_profile"))
        self.bio_label.setText(t("idle_bio"))


class PresetTile(QPushButton):
    def __init__(self, name: str, offset_ms: int, role: str, pocket_name: str, parent=None):
        super().__init__(parent)
        self.preset_name = name
        self.offset_ms = offset_ms
        self.setObjectName("presetTile")
        self.setProperty("presetRole", role)
        self.setProperty("presetActive", "false")
        self.setCheckable(True)
        self.setChecked(False)
        self.setFlat(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(96)
        self.setMinimumWidth(140)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        title = anton_display() if name.startswith("Anton Shcherbakov") else name
        subtitle = f"{pocket_short(pocket_name)}  ·  {offset_ms:+d} ms" if name.startswith("Anton") else f"{offset_ms:+d} ms"
        self.title_label = QLabel(title)
        self.title_label.setObjectName("presetTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        title_font = _reading_font(15)
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: #f6f1e8; background: transparent;")
        self.sub_label = QLabel(subtitle)
        self.sub_label.setObjectName("presetSub")
        self.sub_label.setProperty("presetRole", role)
        self.sub_label.setWordWrap(True)
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        sub_font = _reading_font(13)
        sub_font.setWeight(QFont.Weight.DemiBold)
        self.sub_label.setFont(sub_font)
        self.sub_label.setStyleSheet("color: #ffd27a; background: transparent;")
        layout.addStretch(1)
        layout.addWidget(self.title_label, 2)
        layout.addWidget(self.sub_label, 0)
        layout.addStretch(1)
        self.setToolTip(groove_bio(name))
        self._glass_glow = QGraphicsDropShadowEffect(self)
        self._glass_glow.setBlurRadius(8)
        self._glass_glow.setOffset(0, 1)
        self._glass_glow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(self._glass_glow)

    def set_glass_active(self, active: bool) -> None:
        self.setChecked(active)
        self.setProperty("presetActive", "true" if active else "false")
        layout = self.layout()
        if layout is not None:
            if active:
                layout.setContentsMargins(11, 10, 9, 6)
            else:
                layout.setContentsMargins(10, 8, 10, 8)
        if active:
            self._glass_glow.setBlurRadius(28)
            self._glass_glow.setOffset(0, 0)
            self._glass_glow.setColor(QColor(255, 183, 3, 160))
        else:
            self._glass_glow.setBlurRadius(8)
            self._glass_glow.setOffset(0, 1)
            self._glass_glow.setColor(QColor(0, 0, 0, 90))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.2, 1.2, -1.2, -1.2)
        active = self.isChecked() or self.property("presetActive") == "true"
        _paint_gold_glass(painter, rect, selected=active, radius=10.0)

    def sizeHint(self) -> QSize:
        return QSize(168, 96)


class GlassTabBar(QTabBar):
    @staticmethod
    def _tab_shape(rect: QRectF, radius: float = 10.0) -> QPainterPath:
        path = QPainterPath()
        radius = min(radius, rect.width() * 0.5, rect.height())
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + radius)
        path.arcTo(rect.left(), rect.top(), radius * 2.0, radius * 2.0, 180.0, -90.0)
        path.lineTo(rect.right() - radius, rect.top())
        path.arcTo(rect.right() - radius * 2.0, rect.top(), radius * 2.0, radius * 2.0, 90.0, -90.0)
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        return path

    def _paint_tab_glass(self, painter: QPainter, index: int, selected: bool) -> None:
        rect = QRectF(self.tabRect(index)).adjusted(0.8, 0.8, -0.8, 0.0)
        shape = self._tab_shape(rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(shape)
        glass = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if selected:
            glass.setColorAt(0.00, QColor(255, 255, 255, 46))
            glass.setColorAt(0.16, QColor(0, 229, 255, 32))
            glass.setColorAt(0.42, QColor(255, 255, 255, 14))
            glass.setColorAt(1.00, QColor(0, 229, 255, 10))
        else:
            glass.setColorAt(0.00, QColor(255, 255, 255, 18))
            glass.setColorAt(0.35, QColor(255, 255, 255, 6))
            glass.setColorAt(1.00, QColor(255, 255, 255, 0))
        painter.fillPath(shape, glass)
        spec = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + 9.0))
        spec.setColorAt(0.00, QColor(255, 255, 255, 70 if selected else 28))
        spec.setColorAt(1.00, QColor(255, 255, 255, 0))
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), 9.0), spec)
        if selected:
            painter.setClipping(False)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 255, 255, 78), 1.0))
            painter.drawPath(self._tab_shape(rect.adjusted(2.2, 2.2, -2.2, 0.0), 8.0))
        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        for index in range(self.count()):
            self._paint_tab_glass(painter, index, index == self.currentIndex())
        index = self.currentIndex()
        if index < 0:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(self.tabRect(index))
        text = self.tabText(index)
        font = QFont(self.font())
        font.setWeight(QFont.Weight.Black)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.6)
        _paint_star_letters(painter, rect, text, font)


class BeatLED(QFrame):
    COLORS = {
        "off": ("#0e0d0c", "#282624"),
        "beat": ("#00e5ff", "#7af4ff"),
        "accent": ("#ffb703", "#ffe566"),
    }

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.setFixedSize(30, 30)
        self._set_color("off")

    def _set_color(self, state: str):
        fill, rim = self.COLORS[state]
        self.setStyleSheet(
            f"background:{fill}; border-radius:15px; border:2px solid {rim};"
        )

    def light(self, state: str):
        self._set_color(state)


class GrooveTrainer(QMainWindow):
    TAB_STYLES = [
        STYLE_JAZZ,
        STYLE_FUNK,
        STYLE_ROCK,
        STYLE_FUSION,
        STYLE_MOTOWN,
    ]

    def __init__(self):
        super().__init__()
        global APP_LANG, APP_SKIN
        APP_LANG, APP_SKIN = load_prefs()
        self.setWindowTitle(t("window_title"))
        self.setWindowIcon(_app_icon())
        self.setMinimumSize(1120, 820)
        self.engine = AudioEngine(make_drum_kit())
        self.preset_buttons: list[PresetTile] = []
        self._preset_hosts: dict[str, QWidget] = {}
        self._style_descs: dict[str, QLabel] = {}
        self._active_preset_name = ""
        self._active_pocket = ""
        self._current_style = STYLE_JAZZ
        self._photo_woods = make_boutique_woods()
        self._gen_woods: dict[str, QPixmap] | None = None
        self._woods = self._woods_for_skin(APP_SKIN)
        self._ash = self._woods["ash"]

        self.cover = CoverBackground(self._ash)
        self.setCentralWidget(self.cover)
        root = QVBoxLayout(self.cover)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 4, 0, 0)
        header.setSpacing(8)
        self.brand_title = QLabel(t("brand"))
        self.brand_title.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        _legible_label(self.brand_title, glow="#0a0604")
        self.brand_title.setStyleSheet(
            "font-size: 26px; font-weight: 900; color: #ffffff; "
            "letter-spacing: 0.6px; background: transparent;"
        )
        self.header_by = QLabel(self._header_by_html())
        self.header_by.setObjectName("headerHint")
        self.header_by.setTextFormat(Qt.TextFormat.RichText)
        self.header_by.setWordWrap(False)
        self.header_by.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.header_by.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        shadow = QGraphicsDropShadowEffect(self.header_by)
        shadow.setOffset(1, 1)
        shadow.setBlurRadius(4)
        shadow.setColor(QColor(0, 0, 0, 210))
        self.header_by.setGraphicsEffect(shadow)
        self.header_by.setStyleSheet(
            "color: #f8f9fa; font-size: 12px; font-weight: 600; letter-spacing: 0.35px; "
            "margin-left: 22px; margin-top: 2px; margin-right: 12px; padding: 0px; "
            "background: transparent; border: none;"
        )
        header.addWidget(self.brand_title, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.header_by, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self._build_chrome(), 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header)

        self.analyzer = GrooveAnalyzer(self._woods["analyzer"])
        root.addWidget(self.analyzer, 35)

        controls = QWidget()
        controls.setMaximumHeight(196)
        control_row = QHBoxLayout(controls)
        control_row.setContentsMargins(0, 0, 0, 0)
        control_row.setSpacing(10)
        control_row.addWidget(self._build_transport_card(), 2)
        control_row.addWidget(self._build_beat_matrix(), 0)
        control_row.addWidget(self._build_pocket_audio_card(), 3)
        root.addWidget(controls)

        root.addWidget(self._build_style_tabs(), 65)

        _signals.beat_flash.connect(self._on_beat, Qt.ConnectionType.QueuedConnection)
        self._rebuild_presets(STYLE_JAZZ)
        self._sync_chrome()

    @staticmethod
    def _header_by_html() -> str:
        return (
            f'{t("header_by")} '
            '<span style="color:#ffb703; font-weight:800;">Anton Shcherbakov</span>'
        )

    def _woods_for_skin(self, skin: str) -> dict[str, QPixmap]:
        if skin == "generated":
            if self._gen_woods is None:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    self._gen_woods = make_generated_woods()
                finally:
                    QApplication.restoreOverrideCursor()
            return self._gen_woods
        return self._photo_woods

    def _build_chrome(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("chromeBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        gen_icon = _wood_swatch(_finish_wood_rgb(_synth_wood_rgb("redwood_burl", (56, 36)), WOOD_FINISH["redwood_burl"]))
        self.skin_photo_btn = _make_chrome_chip(t("skin_photo"), _wood_swatch(self._photo_woods["ash"]))
        self.skin_gen_btn = _make_chrome_chip(t("skin_gen"), gen_icon)
        self.lang_en_btn = _make_chrome_chip("ENG", QIcon(_flag_pixmap("us")))
        self.lang_ru_btn = _make_chrome_chip("РУС", QIcon(_flag_pixmap("ru")))
        self.skin_photo_btn.setToolTip(t("skin_photo_tip"))
        self.skin_gen_btn.setToolTip(t("skin_gen_tip"))
        skins = QButtonGroup(bar)
        skins.setExclusive(True)
        skins.addButton(self.skin_photo_btn)
        skins.addButton(self.skin_gen_btn)
        langs = QButtonGroup(bar)
        langs.setExclusive(True)
        langs.addButton(self.lang_en_btn)
        langs.addButton(self.lang_ru_btn)
        self.skin_photo_btn.clicked.connect(lambda: self._set_skin("photo"))
        self.skin_gen_btn.clicked.connect(lambda: self._set_skin("generated"))
        self.lang_en_btn.clicked.connect(lambda: self._set_lang("en"))
        self.lang_ru_btn.clicked.connect(lambda: self._set_lang("ru"))
        row.addWidget(self.skin_photo_btn)
        row.addWidget(self.skin_gen_btn)
        row.addSpacing(8)
        row.addWidget(self.lang_en_btn)
        row.addWidget(self.lang_ru_btn)
        return bar

    def _sync_chrome(self) -> None:
        self.skin_photo_btn.setChecked(APP_SKIN == "photo")
        self.skin_gen_btn.setChecked(APP_SKIN == "generated")
        self.lang_en_btn.setChecked(APP_LANG == "en")
        self.lang_ru_btn.setChecked(APP_LANG == "ru")

    def _set_skin(self, skin: str) -> None:
        global APP_SKIN
        if APP_SKIN == skin:
            return
        APP_SKIN = skin
        save_prefs()
        self._woods = self._woods_for_skin(skin)
        self._ash = self._woods["ash"]
        self.cover.set_ash(self._ash)
        self.analyzer.set_wood(self._woods["analyzer"])
        self._rebuild_presets(self._current_style)
        self._sync_chrome()

    def _set_lang(self, lang: str) -> None:
        global APP_LANG
        if APP_LANG == lang:
            return
        APP_LANG = lang
        save_prefs()
        self._retranslate()
        self._sync_chrome()

    def _retranslate(self) -> None:
        self.setWindowTitle(t("window_title"))
        self.brand_title.setText(t("brand"))
        self.header_by.setText(self._header_by_html())
        self.skin_photo_btn.setText(t("skin_photo"))
        self.skin_gen_btn.setText(t("skin_gen"))
        self.skin_photo_btn.setToolTip(t("skin_photo_tip"))
        self.skin_gen_btn.setToolTip(t("skin_gen_tip"))
        self.transport_header.setText(t("transport"))
        self.start_btn.setText(t("stop") if self.engine.running else t("start"))
        self.reset_btn.setText(t("clear"))
        self.beat_header.setText(t("beat_matrix"))
        self.pocket_header.setText(t("pocket_audio"))
        self.lbl_metro_grid.setText(t("metro_grid"))
        self.lbl_micro.setText(t("micro_offset"))
        self.offset_hint.setText(t("offset_hint"))
        self.lbl_levels.setText(t("audio_levels"))
        self.lbl_drums.setText(t("drums"))
        self.lbl_metro.setText(t("metronome"))
        self.lbl_pitch.setText(t("click_pitch"))
        self.subdivision_combo.blockSignals(True)
        self.subdivision_combo.setItemText(0, t("quarters"))
        self.subdivision_combo.setItemText(1, t("eighths"))
        self.subdivision_combo.blockSignals(False)
        for index, style_key in enumerate(self.TAB_STYLES):
            self.tabs.setTabText(index, style_tab_label(style_key))
            desc = self._style_descs[style_key]
            desc.setText(style_description(style_key))
            desc.setFont(_reading_font(16))
        pocket = pocket_title(self._active_pocket) if self._active_pocket else ""
        self.analyzer.retranslate(
            style_tab_label(self._current_style),
            self._active_preset_name,
            pocket,
            self.offset_slider.value(),
        )
        self._rebuild_presets(self._current_style)

    def _make_card(self, title_text: str) -> tuple[QFrame, QVBoxLayout, QLabel]:
        card = QFrame()
        card.setObjectName("card")
        _elevate(card, blur=22, y=3, alpha=120)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        header = QLabel(title_text)
        header.setObjectName("cardHeader")
        layout.addWidget(header)
        return card, layout, header

    def _build_transport_card(self) -> QFrame:
        card, layout, self.transport_header = self._make_card(t("transport"))
        bpm_row = QHBoxLayout()
        bpm_label = QLabel("BPM")
        bpm_label.setObjectName("sectionLabel")
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setObjectName("bpmSpin")
        self.bpm_spin.setRange(40, 240)
        self.bpm_spin.setValue(100)
        self.bpm_spin.valueChanged.connect(self._set_bpm)
        self.bpm_slider = QSlider(Qt.Orientation.Horizontal)
        self.bpm_slider.setRange(40, 240)
        self.bpm_slider.setValue(100)
        self.bpm_slider.valueChanged.connect(self.bpm_spin.setValue)
        self.bpm_spin.valueChanged.connect(self.bpm_slider.setValue)
        bpm_row.addWidget(bpm_label)
        bpm_row.addWidget(self.bpm_spin)
        bpm_row.addWidget(self.bpm_slider, 1)
        layout.addLayout(bpm_row)
        self.start_btn = QPushButton(t("start"))
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setProperty("playing", "false")
        self.start_btn.setMinimumHeight(44)
        self.start_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self.start_btn)
        self.reset_btn = QPushButton(t("clear"))
        self.reset_btn.setMinimumHeight(32)
        self.reset_btn.clicked.connect(self._reset_profile)
        layout.addWidget(self.reset_btn)
        return card

    def _build_beat_matrix(self) -> QFrame:
        card = QFrame()
        card.setObjectName("innerCard")
        _elevate(card, blur=18, y=2, alpha=100)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        self.beat_header = QLabel(t("beat_matrix"))
        self.beat_header.setObjectName("cardHeader")
        layout.addWidget(self.beat_header)
        led_row = QHBoxLayout()
        led_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        led_row.setSpacing(10)
        self.leds: list[BeatLED] = []
        for i in range(PATTERN_LEN):
            led = BeatLED(i)
            self.leds.append(led)
            led_row.addWidget(led)
        layout.addLayout(led_row)
        layout.addStretch(1)
        return card

    def _build_pocket_audio_card(self) -> QFrame:
        card, layout, self.pocket_header = self._make_card(t("pocket_audio"))
        inner = QHBoxLayout()
        pocket = QFrame()
        pocket.setObjectName("innerCard")
        pocket_layout = QVBoxLayout(pocket)
        pocket_layout.setContentsMargins(10, 10, 10, 10)
        pocket_layout.setSpacing(6)
        self.lbl_metro_grid = self._section_label(t("metro_grid"))
        pocket_layout.addWidget(self.lbl_metro_grid)
        self.subdivision_combo = QComboBox()
        self.subdivision_combo.addItem(t("quarters"), SUBDIVISION_QUARTERS)
        self.subdivision_combo.addItem(t("eighths"), SUBDIVISION_EIGHTHS)
        self.subdivision_combo.currentIndexChanged.connect(self._set_subdivision)
        pocket_layout.addWidget(self.subdivision_combo)
        self.lbl_micro = self._section_label(t("micro_offset"))
        pocket_layout.addWidget(self.lbl_micro)
        offset_row = QHBoxLayout()
        self.offset_slider = QSlider(Qt.Orientation.Horizontal)
        self.offset_slider.setRange(-50, 50)
        self.offset_slider.setValue(0)
        self.offset_slider.valueChanged.connect(self._offset_changed)
        self.offset_label = QLabel("0 ms")
        self.offset_label.setObjectName("valueLabel")
        self.offset_label.setFixedWidth(72)
        offset_row.addWidget(self.offset_slider, 1)
        offset_row.addWidget(self.offset_label)
        pocket_layout.addLayout(offset_row)
        self.offset_hint = QLabel(t("offset_hint"))
        self.offset_hint.setObjectName("hintLabel")
        pocket_layout.addWidget(self.offset_hint)
        inner.addWidget(pocket, 1)

        levels = QFrame()
        levels.setObjectName("innerCard")
        levels_layout = QVBoxLayout(levels)
        levels_layout.setContentsMargins(10, 10, 10, 10)
        levels_layout.setSpacing(6)
        self.lbl_levels = self._section_label(t("audio_levels"))
        levels_layout.addWidget(self.lbl_levels)
        self.drum_vol_slider = self._make_percent_slider(80)
        self.drum_vol_label = QLabel("80%")
        self.drum_vol_label.setObjectName("valueLabel")
        self.drum_vol_slider.valueChanged.connect(self._set_drum_volume)
        drums_row, self.lbl_drums = self._slider_row(t("drums"), self.drum_vol_slider, self.drum_vol_label)
        levels_layout.addLayout(drums_row)
        self.metro_vol_slider = self._make_percent_slider(80)
        self.metro_vol_label = QLabel("80%")
        self.metro_vol_label.setObjectName("valueLabel")
        self.metro_vol_slider.valueChanged.connect(self._set_metro_volume)
        metro_row, self.lbl_metro = self._slider_row(t("metronome"), self.metro_vol_slider, self.metro_vol_label)
        levels_layout.addLayout(metro_row)
        self.pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self.pitch_slider.setRange(400, 1500)
        self.pitch_slider.setValue(1000)
        self.pitch_slider.valueChanged.connect(self._set_pitch)
        self.pitch_label = QLabel("1000 Hz")
        self.pitch_label.setObjectName("valueLabel")
        pitch_row, self.lbl_pitch = self._slider_row(t("click_pitch"), self.pitch_slider, self.pitch_label)
        levels_layout.addLayout(pitch_row)
        inner.addWidget(levels, 1)
        layout.addLayout(inner)
        return card

    def _build_style_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabBar(GlassTabBar())
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setDrawBase(False)
        for style_key in self.TAB_STYLES:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(10, 10, 10, 10)
            shell = GlassPlate(dim=True)
            shell.setObjectName("readPlate")
            shell_layout = QVBoxLayout(shell)
            shell_layout.setContentsMargins(14, 10, 14, 10)
            desc = QLabel(style_description(style_key))
            desc.setObjectName("grooveCopy")
            desc.setWordWrap(True)
            desc.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            desc.setFont(_reading_font(16))
            _legible_label(desc, color="#f0eadf", glow="#000000")
            desc.setFont(_reading_font(16))
            self._style_descs[style_key] = desc
            shell_layout.addWidget(desc)
            tab_layout.addWidget(shell)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            host = QWidget()
            host_layout = QGridLayout(host)
            host_layout.setContentsMargins(0, 0, 4, 0)
            host_layout.setHorizontalSpacing(12)
            host_layout.setVerticalSpacing(0)
            self._preset_hosts[style_key] = host
            scroll.setWidget(host)
            tab_layout.addWidget(scroll, 1)
            self.tabs.addTab(tab, style_tab_label(style_key))
        self.tabs.currentChanged.connect(self._on_tab_changed)
        return self.tabs

    def _rebuild_presets(self, style: str):
        host = self._preset_hosts[style]
        layout = host.layout()
        self._clear_layout(layout)
        self.preset_buttons = []
        pockets = list(GENRE_PRESETS[style].items())
        row_count = max(len(presets) for _, presets in pockets)
        for column, (pocket_name, presets) in enumerate(pockets):
            block = WoodPanel(
                self._woods[POCKET_WOOD[pocket_name]],
                POCKET_INLAY[pocket_name],
                "presetBlock",
            )
            block.setProperty("tint", POCKET_TINTS[pocket_name])
            _elevate(block, blur=32, y=5, alpha=155)
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(12, 12, 12, 12)
            block_layout.setSpacing(10)
            heading = QLabel(pocket_title(pocket_name).upper())
            heading.setObjectName("pocketHeading")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            heading.setFixedHeight(24)
            head_font = _reading_font(14)
            head_font.setWeight(QFont.Weight.DemiBold)
            heading.setFont(head_font)
            heading.setStyleSheet("color: #ffe7a8; background: transparent;")
            head_plate = GlassPlate(dim=True)
            head_plate.setFixedHeight(32)
            head_layout = QVBoxLayout(head_plate)
            head_layout.setContentsMargins(8, 2, 8, 2)
            head_layout.addWidget(heading)
            block_layout.addWidget(head_plate)
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)
            role = POCKET_ROLES[pocket_name]
            for row, (name, value) in enumerate(presets):
                tile = PresetTile(name, value, role, pocket_name)
                tile.clicked.connect(
                    lambda _=False, n=name, v=value, p=pocket_name: self._apply_preset(n, v, p)
                )
                grid.addWidget(tile, row, 0)
                grid.setRowMinimumHeight(row, 96)
                self.preset_buttons.append(tile)
            for row in range(len(presets), row_count):
                spacer = QWidget()
                spacer.setFixedHeight(96)
                grid.addWidget(spacer, row, 0)
                grid.setRowMinimumHeight(row, 96)
            grid.setColumnStretch(0, 1)
            block_layout.addLayout(grid, 1)
            layout.addWidget(block, 0, column)
            layout.setColumnStretch(column, 1)
        self._refresh_active_preset()

    @staticmethod
    def _clear_layout(layout: QLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child is not None:
                GrooveTrainer._clear_layout(child)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    @staticmethod
    def _make_percent_slider(default: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(default)
        return slider

    @staticmethod
    def _slider_row(label_text: str, slider: QSlider, value_label: QLabel) -> tuple[QHBoxLayout, QLabel]:
        row = QHBoxLayout()
        caption = QLabel(label_text)
        row.addWidget(caption)
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        return row, caption

    def _on_tab_changed(self, index: int):
        if index < 0:
            return
        style_key = self.TAB_STYLES[index]
        self._current_style = style_key
        self.engine.set_style(style_key)
        self._rebuild_presets(style_key)
        genre = style_tab_label(style_key)
        if not self._active_preset_name:
            self.analyzer.clear_profile(genre)
        else:
            self.analyzer.genre_label.setText(f"{t('tab_genre')}  ·  {genre}")

    def _toggle_play(self):
        if self.engine.running:
            self.engine.stop()
            self.start_btn.setText(t("start"))
            self.start_btn.setProperty("playing", "false")
            for led in self.leds:
                led.light("off")
        else:
            self.engine.start()
            self.start_btn.setText(t("stop"))
            self.start_btn.setProperty("playing", "true")
            for led in self.leds:
                led.light("off")
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)

    def _reset_profile(self):
        self._active_preset_name = ""
        self._active_pocket = ""
        self._mark_preset("")
        self.analyzer.clear_profile(style_tab_label(self._current_style))

    def _set_bpm(self, value: int):
        self.engine.set_bpm(value)

    def _set_subdivision(self, _index: int = 0):
        key = self.subdivision_combo.currentData()
        if not key:
            return
        with self.engine._lock:
            self.engine.metronome_subdivision = key

    def _offset_changed(self, value: int):
        with self.engine._lock:
            self.engine.micro_offset_ms = value
        self.offset_label.setText(f"{value:+d} ms" if value else "0 ms")
        self._refresh_active_preset()

    def _apply_preset(self, name: str, value: int, pocket: str):
        self._active_preset_name = name
        self._active_pocket = pocket
        self.offset_slider.blockSignals(True)
        self.offset_slider.setValue(value)
        self.offset_slider.blockSignals(False)
        with self.engine._lock:
            self.engine.micro_offset_ms = value
        self.offset_label.setText(f"{value:+d} ms" if value else "0 ms")
        self.analyzer.show_musician(name, pocket_title(pocket), style_tab_label(self._current_style), value)
        self._mark_preset(name)

    def _mark_preset(self, name: str):
        for button in self.preset_buttons:
            button.set_glass_active(button.preset_name == name)

    def _current_pool(self) -> dict[str, list[tuple[str, int]]]:
        return GENRE_PRESETS[self._current_style]

    def _refresh_active_preset(self):
        current = self.offset_slider.value()
        matched = None
        for presets in self._current_pool().values():
            for name, value in presets:
                if name == self._active_preset_name and value == current:
                    matched = name
                    break
                if matched is None and value == current:
                    matched = name
            if matched == self._active_preset_name:
                break
        self._mark_preset(matched or "")

    def _set_drum_volume(self, value: int):
        with self.engine._lock:
            self.engine.drum_vol = value / 100.0
        self.drum_vol_label.setText(f"{value}%")

    def _set_metro_volume(self, value: int):
        with self.engine._lock:
            self.engine.metro_vol = value / 100.0
        self.metro_vol_label.setText(f"{value}%")

    def _set_pitch(self, value: int):
        with self.engine._lock:
            self.engine.metro_freq = float(value)
        self.pitch_label.setText(f"{value} Hz")

    def _on_beat(self, step: int):
        if not self.leds:
            return
        for index, led in enumerate(self.leds):
            if index == step:
                led.light("accent" if index in {0, 4} else "beat")
            else:
                led.light("off")

    def closeEvent(self, event):
        self.engine.shutdown()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Groove Trainer")
    app.setOrganizationName("Anton Shcherbakov")
    icon = _app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    app.setStyleSheet(DARK_STYLE)
    window = GrooveTrainer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
