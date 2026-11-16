"""AI ҰБТ Mentor 4.0 — теория, тараулық тесттер және 25 оқу нұсқасы."""
import csv
import io
import json
from pathlib import Path
import random
import sqlite3
from uuid import uuid4
import streamlit as st
import inspect
import importlib
import mentor_core as _mentor_core
# Streamlit қайта жүктегенде ескі функция жадта қалса, дискідегі модульді қайта оқу.
if 'delivery' not in inspect.signature(_mentor_core.save_attempt).parameters:
    _mentor_core = importlib.reload(_mentor_core)
import sheets_sync
from auth_ui import render_auth, sign_out, user_from_session
from mentor_core import answer_complete, grade, history, load_content, plan, question_points, save_attempt

st.set_page_config(page_title='AI ҰБТ Mentor', page_icon='🎓', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container{max-width:1120px;padding-top:2rem;}h1,h2,h3{letter-spacing:-.025em;}
.hero{background:linear-gradient(115deg,#122448,#244b91);padding:32px;border-radius:22px;color:white;margin-bottom:24px;}
.hero h1{color:white;margin:8px 0;font-size:2.6rem;}.hero p{color:#dce7ff;max-width:700px;}
.tag{font-size:.8rem;letter-spacing:.12em;color:#9fc6ff;}
div[data-testid="stMetric"]{background:transparent;color:inherit;border:1px solid rgba(128,145,170,.45);border-radius:14px;padding:16px;}
.stButton button{border-radius:10px;min-height:44px;}
/* Белгіше қарпі жүктелмесе, ағылшынша лигатура орнына қазақша мәтін. */
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"]{display:none!important;}
[data-testid="stSidebarCollapseButton"] button > *,
[data-testid="stExpandSidebarButton"] button > *{display:none!important;}
[data-testid="stSidebarCollapseButton"] button::after{content:"Жасыру";font-family:sans-serif;font-size:12px;}
[data-testid="stExpandSidebarButton"] button::after{content:"Мәзір";font-family:sans-serif;font-size:12px;}
[data-testid="stSidebarNav"]{display:none;}
@media(max-width:600px){.hero{padding:20px;}.hero h1{font-size:2rem;}}
</style>''', unsafe_allow_html=True)
QUESTIONS, CHAPTERS, VARIANTS = load_content()
CHAPTER_TESTS = json.loads((Path(__file__).parent / 'chapter_tests.json').read_text(encoding='utf-8'))
BY_ID = {q['id']: q for q in QUESTIONS}
TOPICS = [c['topic'] for c in CHAPTERS]
PAGES = ['Басты бет', 'Теория және тараулық тест', 'Тест тапсыру', 'ҰБТ-ға дайындық: 25 нұсқа', 'Менің нәтижелерім', 'Жеке дайындық жоспары']
TYPES = {'single': 'Бір дұрыс жауап', 'context': 'Мәнмәтін бойынша бір жауап', 'multi': 'Бір немесе бірнеше дұрыс жауап', 'match': 'Сәйкестендіру'}
SOURCE = 'https://testcenter.kz/wp-content/uploads/2025/10/28_%D0%98%D0%BD%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D1%82%D0%B8%D0%BA%D0%B0_%D0%BA%D0%B0%D0%B7.pdf'

def go(page):
    st.session_state.page = page

def start_quiz(questions, title, page=None):
    # Жаңа әрекетте ескі жауап кілттерін тазалау.
    for key in list(st.session_state):
        if key.startswith('ans_'):
            del st.session_state[key]
    st.session_state.quiz = questions
    st.session_state.quiz_title = title
    st.session_state.attempt_id = str(uuid4())
    st.session_state.pop('result', None)
    if page:
        go(page)

def chapter_start(topic):
    test = next(t for t in CHAPTER_TESTS if t['topic'] == topic)
    questions = [BY_ID[qid] for qid in test['question_ids']]
    start_quiz(questions, f'Тараулық тест · {topic}', PAGES[2])

def option_label(value):
    return f'`{value}`' if '<' in value or '$' in value else value

def answer_text(q, a):
    if q.get('type') == 'match':
        return '\n'.join(f"{left} → {q['options'][value]}" for left, value in zip(q['left'], a))
    if isinstance(a, list):
        return '; '.join(q['options'][v] for v in sorted(a))
    return q['options'][a]

def show_result(result):
    st.success(f"Дұрыс орындалған тапсырма: {result['score']} / {result['total']}")
    st.metric('Оқу ұпайы', f"{result.get('points', result['score'])} / {result.get('max_points', result['total'])}")
    st.progress(result['percent'] / 100, text=f"Оқу нәтижесі: {result['percent']}%")
    st.caption('Бұл — жаттығу нәтижесі. ҰБТ балының болжамы емес. Көп жауапты және сәйкестендіруде тек толық дұрыс жауапқа 2 ұпай, өзгесіне 0 беріледі; ресми ішінара бағалау ережесі қолданылмайды.')
    wrong_topics = list(dict.fromkeys(q['topic'] for q in result['details'] if not q['correct']))
    if wrong_topics:
        st.info('Қайталауға ұсынылатын тараулар: ' + ', '.join(wrong_topics))
    for i, q in enumerate(result['details'], 1):
        with st.expander(f"{'✓' if q['correct'] else '✗'} {i}. {q['topic']} · {q['text'].splitlines()[0]}"):
            if q.get('context'):
                st.text(q['context'])
            st.text(q['text'])
            st.write('Сіздің жауабыңыз:')
            st.text(answer_text(q, q['selected']))
            st.write('Дұрыс жауап:')
            st.text(answer_text(q, q['answer']))
            st.info(q['explanation'])
            st.caption('Келесі қадам: осы тақырыптың теориясын оқып, тараулық тестті қайта орындаңыз.')

def show_sheets_status(profile, auto_attempt=None):
    url, secret = sheets_sync.settings()
    if not url and not secret:
        st.caption('Мұғалімнің Google кестесіне жіберу қосылымы әзірге бапталмаған.')
        return
    stats = sheets_sync.counts(profile)
    if stats['pending'] and auto_attempt and st.session_state.get('last_auto_sync') != auto_attempt:
        st.session_state.last_auto_sync = auto_attempt
        with st.spinner('Нәтижені мұғалімнің кестесіне жіберіп жатырмыз…'):
            outcome = sheets_sync.sync_pending(profile, url, secret, limit=1)
        stats = sheets_sync.counts(profile)
        if not outcome['configured']:
            st.warning('Кесте қосылымының баптауы толық емес. Нәтиже сайтта сақталды.')
    if stats['sent']:
        st.caption(f"Мұғалімнің Google кестесіне жеткізілген нәтиже: {stats['sent']}.")
    if stats['pending']:
        st.warning(f"Кестеге жіберуді күтіп тұрған нәтиже: {stats['pending']}. Сайттағы нәтиже сақталған; байланыс қалпына келгенде қайта жіберіңіз.")
        if st.button('Кестеге жіберуді қайталау', key='retry_sheets'):
            with st.spinner('Кестеге жіберіп жатырмыз…'):
                outcome = sheets_sync.sync_pending(profile, url, secret, limit=3)
            if outcome['failed'] or not outcome['configured']:
                st.warning('Қазір жіберілмеді. Нәтижені CSV арқылы жүктеп алыңыз, кейін қайта көріңіз.')
            else:
                st.success(f"Жеткізілген нәтиже: {outcome['sent']}.")

def render_quiz(profile):
    if 'quiz' not in st.session_state:
        st.info('Алдымен тест таңдаңыз немесе теория бөліміндегі тараулық тестті бастаңыз.')
        return
    st.subheader(st.session_state.quiz_title)
    if 'result' in st.session_state:
        show_sheets_status(profile, st.session_state.attempt_id)
        show_result(st.session_state.result)
        a, b = st.columns(2)
        a.button('Теорияны қайталау', on_click=go, args=(PAGES[1],), key='review_theory')
        b.button('Жеке жоспарға өту', on_click=go, args=(PAGES[5],))
        return
    quiz = st.session_state.quiz
    st.caption(f"{len(quiz)} тапсырма · ең көбі {sum(question_points(q) for q in quiz)} оқу ұпайы. Жаңа тест бастамасаңыз, бөлім ауыстырғанда ағымдағы тестіңіз жалғасады.")
    with st.form('quiz_form'):
        answers = []
        context_seen = set()
        for i, q in enumerate(quiz, 1):
            if q.get('context_id') and q['context_id'] not in context_seen:
                st.info('Келесі 5 тапсырмаға ортақ мәнмәтін')
                st.text(q['context'])
                context_seen.add(q['context_id'])
            kind = q.get('type', 'single')
            st.markdown(f"**{i}. {q['topic']}**")
            st.caption(f"{TYPES[kind]} · {question_points(q)} оқу ұпайы")
            st.text(q['text'])
            key = f"ans_{st.session_state.attempt_id}_{q['id']}"
            opts = range(len(q['options']))
            label = lambda x, q=q: option_label(q['options'][x])
            if kind == 'multi':
                answer = st.multiselect(f'{i}-тапсырма: барлық дұрыс жауаптарды таңдаңыз', opts, format_func=label, key=key, placeholder='Жауаптарды таңдаңыз')
            elif kind == 'match':
                st.caption('Әр сол жақ ұғымға оң жақтағы бір нұсқаны таңдаңыз.')
                answer = [st.selectbox(f'{i}.{j+1} · {left}', opts, format_func=label, index=None, placeholder='Сәйкес нұсқаны таңдаңыз', key=f'{key}_{j}') for j, left in enumerate(q['left'])]
            else:
                answer = st.radio(f'{i}-тапсырманың жауабы', opts, format_func=label, index=None, key=key)
            answers.append(answer)
            st.divider()
        submitted = st.form_submit_button('Тестті аяқтау', type='primary')
    if submitted:
        missing = [str(i) for i, (q, a) in enumerate(zip(quiz, answers), 1) if not answer_complete(q, a)]
        if missing:
            st.warning('Толтырылмаған тапсырмалар: ' + ', '.join(missing) + '. Жауаптарды таңдап, қайта аяқтаңыз.')
        else:
            result = grade(quiz, answers)
            result['title'] = st.session_state.quiz_title
            try:
                save_attempt(st.session_state.attempt_id, profile, result, delivery=sheets_sync.delivery_payload(user, result))
            except (sqlite3.Error, OSError):
                st.error('Нәтижені сақтау мүмкін болмады. Қалтаға жазу рұқсатын тексеріп, қайта басыңыз.')
            else:
                st.session_state.result = result
                st.rerun()

# Бұрынғы ашық сессиядан жаңартқанда ескі тест күйін тазарту. Нәтижелер базасы өзгермейді.
if st.session_state.get('app_version') != 4:
    for old_key in ['quiz', 'result', 'quiz_title', 'attempt_id']:
        st.session_state.pop(old_key, None)
    st.session_state.app_version = 4
if st.session_state.get('page', PAGES[0]) not in PAGES:
    st.session_state.page = PAGES[0]

try:
    user = user_from_session()
except (sqlite3.Error, OSError):
    st.error('Есептік жазбалар базасы ашылмады. Деректер қалтасын тексеріңіз.')
    st.stop()
profile = user['profile'] if user else None

with st.sidebar:
    st.title('🎓 AI ҰБТ Mentor')
    st.caption('ИНФОРМАТИКА · 10–11-СЫНЫП · 4.0')
    if user:
        st.write(f"{user['username']} · {user['school_class']}")
        st.button('Есептік жазбадан шығу', on_click=sign_out)
    else:
        st.caption('Қонақ режимі · теорияны еркін оқыңыз')
    st.radio('Бөлімдер', PAGES, key='page')
    st.divider()
    st.caption('Теория → мысал → тараулық тест → қате талдау → қайта орындау')
    st.caption('Ақылы API жоқ. Жеке жоспар ережелер бойынша құрылады.')
    st.caption('Нәтижелер жеке есептік жазбаңызда сақталады. Қосылым бапталса, пайдаланушы аты, сынып және тест қорытындысы мұғалімнің Google кестесіне жіберіледі; құпиясөз жіберілмейді.')
if st.session_state.page not in PAGES[:2] and not user:
    render_auth()
    st.stop()
if st.session_state.get('owner') != profile:
    for key in ['quiz', 'result', 'quiz_title', 'attempt_id']:
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith('ans_'):
            del st.session_state[key]
    st.session_state.owner = profile
try:
    records = history(profile) if profile else []
except (sqlite3.Error, OSError):
    st.error('Нәтижелер базасы ашылмады. data қалтасына жазу рұқсатын және дискідегі бос орынды тексеріңіз.')
    st.stop()
page = st.session_state.page

if page == PAGES[0]:
    st.markdown('''<div class="hero"><div class="tag">ОҚЫ · ТҮСІН · ӨЗІҢДІ ТЕКСЕР</div><h1>ҰБТ-ға сенімді қадам</h1><p>Қазақша теорияны меңгеріп, тараулық тестпен біліміңді бекіт. 25 оқу нұсқасында жаттығып, өз нәтижелеріңді бақыла.</p></div>''', unsafe_allow_html=True)
    a,b,c,d = st.columns(4)
    a.metric('Теория тарауы', len(CHAPTERS))
    b.metric('Тапсырма қоры', len(QUESTIONS))
    c.metric('Дайындық нұсқасы', len(VARIANTS))
    d.metric('Орындалған тест', len(records))
    st.subheader('Бүгінгі дайындық')
    cards = [(PAGES[1], '13 тарау: теория, мысал және 40 тапсырмаға арналған 50 ұпайлық тест.', 'Теориядан бастау →'), (PAGES[3], 'Әр нұсқада 40 тапсырма: дара жауап, мәнмәтін, көп жауап және сәйкестендіру.', 'Нұсқа таңдау →'), (PAGES[5], 'Нәтижеңе сүйенген жеті күндік дайындық жоспары.', 'Жоспарды ашу →')]
    for col, (title, text, button) in zip(st.columns(3), cards):
        with col, st.container(border=True):
            st.subheader(title)
            st.write(text)
            st.button(button, on_click=go, args=(title,), width='stretch')
    st.info('620 авторлық тапсырма ортақ қорда сақталған. 25 нұсқада сұрақтар ішінара қайталанады; бұл 1000 бірегей сұрақ дегенді білдірмейді. Нұсқалар — ресми ҰБТ тесттері емес.')
    with st.expander('Мазмұн негізі және оқу бағалауы'):
        st.markdown(f'[ҰТО: информатикадан 2026 жылдан қолданылатын спецификация]({SOURCE})')
        st.write('13 тақырып бағыты мен 40 тапсырманың түрлерге бөлінуі осы құжатқа сүйенеді. Теория мен сұрақтар авторлық түрде жазылған, ресми тапсырмалар көшірілмеген.')
        st.write('Оқу шкаласы: бір жауапты және мәнмәтін тапсырмасына 1 ұпай; көп жауапты және сәйкестендіруге тек толық дұрыс болса 2 ұпай, әйтпесе 0. Ресми ішінара бағалау мен A/B/C қиындық үлестеріне сәйкестік расталмаған. Уақыт шектеуі жоқ.')
        st.caption('Python, SQL, HTML командалары мен халықаралық функция атаулары аударылмайды. Олардың шарттары мен түсіндірмелері қазақша.')

elif page == PAGES[1]:
    st.title('Теория және тараулық тест')
    st.write('Алдымен теорияны оқыңыз, мысалды түсіндіріп көріңіз, содан кейін осы тараудың тестін орындаңыз.')
    topic = st.selectbox('Тарауды таңдаңыз', TOPICS, key='theory_topic')
    chapter = next(c for c in CHAPTERS if c['topic'] == topic)
    st.subheader(f"{chapter['id']:02}. {topic}")
    st.caption('Теория → шешілген мысал → 40 тапсырма → нәтиже мен түсіндірме')
    st.markdown(chapter['theory'])
    st.subheader('Шешілген мысал')
    st.text(chapter['example'])
    st.warning('Жиі кездесетін қате: ' + chapter['mistake'])
    st.info('Әр тараулық тестте 40 тапсырма, ең көбі 50 оқу ұпайы бар. Өзіңізді тексеріңіз: негізгі ережені өз сөзіңізбен айтыңыз, мысалды қарамай қайта шешіңіз. Содан кейін 40 тапсырмалық тарау тестін орындаңыз.')
    if user:
        st.button('Тарау тестін бастау · 40 тапсырма / 50 ұпай', type='primary', on_click=chapter_start, args=(topic,))
    else:
        st.button('Тест үшін кіру немесе тіркелу', type='primary', on_click=go, args=(PAGES[2],))
    st.caption('Тест аяқталған соң әр жауаптың түсіндірмесін ашып, қате кеткен ережені қайталаңыз. Тараулық тестті қайта бастауға болады.')

elif page == PAGES[2]:
    st.title('Тест тапсыру')
    st.info('Толық дайындық нұсқасы: 40 тапсырма / 50 оқу ұпайы. Қысқа жаттығу бөлек параметрмен таңдалады.')
    with st.expander('Жылдам жаттығу параметрлері', expanded='quiz' not in st.session_state):
        mode = st.radio('Тест көлемі', ['Толық тест · 40 тапсырма / 50 ұпай', 'Қысқа жаттығу'], key='practice_mode')
        topic = st.selectbox('Тақырып', ['Барлық тақырыптар'] + TOPICS)
        st.caption('Жаңа тест ағымдағы аяқталмаған тестті ауыстырады.')
        if mode == 'Қысқа жаттығу':
            pool = [q for q in QUESTIONS if q['type'] == 'single' and (topic == 'Барлық тақырыптар' or q['topic'] == topic)]
            count = st.selectbox('Сұрақ саны', [n for n in [4,8,16,25] if n <= len(pool)])
            if st.button('Жаңа тест бастау', type='primary'):
                start_quiz(random.sample(pool, count), f'Қысқа жаттығу · {topic}')
        elif st.button('Жаңа тест бастау', type='primary'):
            if topic == 'Барлық тақырыптар':
                variant = random.choice(VARIANTS)
                start_quiz([BY_ID[qid] for qid in variant['question_ids']], f"{variant['number']:02}-нұсқа · 40 тапсырма / 50 ұпай")
            else:
                test = next(t for t in CHAPTER_TESTS if t['topic'] == topic)
                start_quiz([BY_ID[qid] for qid in test['question_ids']], f'Тараулық тест · {topic}')
    render_quiz(profile)

elif page == PAGES[3]:
    st.title('ҰБТ-ға дайындық: 25 нұсқа')
    st.write('Құрылымы: 25 дара жауапты + бір мәнмәтінге 5 сұрақ + 5 көп жауапты + 5 сәйкестендіру = 40 тапсырма.')
    st.info('Бұлар — авторлық оқу нұсқалары. Ортақ қордан алынған сұрақтар нұсқалар арасында қайталануы мүмкін. Бір нұсқаны қайта таңдағанда оның сұрақтары өзгермейді.')
    st.caption('Ең көбі 50 оқу ұпайы. Көп жауап пен сәйкестендіруде тек толық дұрыс жауап бағаланады; ресми ішінара бағалау қолданылмайды. Қиындық деңгейлерінің ресми үлесіне сәйкестік расталмаған.')
    number = st.selectbox('Нұсқаны таңдаңыз', range(1,26), format_func=lambda n: f'{n:02}-нұсқа · 40 тапсырма')
    st.caption('Нұсқаны бастау ағымдағы аяқталмаған тестті ауыстырады.')
    if st.button('Таңдалған нұсқаны бастау', type='primary'):
        variant = next(v for v in VARIANTS if v['number'] == number)
        start_quiz([BY_ID[qid] for qid in variant['question_ids']], f'{number:02}-нұсқа · ҰБТ-ға дайындық')
    render_quiz(profile)

elif page == PAGES[4]:
    st.title('Менің нәтижелерім')
    show_sheets_status(profile)
    if not records:
        st.info('Әзірге нәтиже жоқ. Алдымен тараулық тест немесе дайындық нұсқасын орындаңыз.')
        st.button('Теорияға өту', on_click=go, args=(PAGES[1],))
    else:
        a,b,c = st.columns(3)
        a.metric('Тест саны', len(records))
        b.metric('Соңғы оқу нәтижесі', f"{records[0]['percent']}%")
        c.metric('Ең жақсы оқу нәтижесі', f"{max(r['percent'] for r in records)}%")
        rows = [{'Уақыты (Қазақстан)': r['created'][:19].replace('T',' '), 'Тест': r.get('title', 'Бастапқы нұсқадағы тест'), 'Дұрыс тапсырма': r['score'], 'Тапсырма саны': r['total'], 'Оқу ұпайы': r.get('points',r['score']), 'Ең көп ұпай': r.get('max_points',r['total']), 'Нәтиже (%)':r['percent']} for r in records]
        st.dataframe(rows, hide_index=True, width='stretch')
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
        st.download_button('Нәтижелерді жүктеу (CSV)', out.getvalue().encode('utf-8-sig'), 'natizheler.csv', 'text/csv')
        st.caption('Әртүрлі тарау мен тапсырма құрамындағы тест нәтижелері бірдей қиындықты білдірмейді. Бұрынғы нәтижелер де сақталады.')
        selected = st.selectbox('Талдауға арналған тест', range(len(records)), format_func=lambda i:f"{records[i]['created'][:19].replace('T',' ')} · {records[i].get('title','Бастапқы тест')} · {records[i]['percent']}%")
        record = records[selected]
        st.subheader('Тақырыптар бойынша дұрыс орындалған тапсырмалар')
        for topic, stat in record['topics'].items():
            st.progress(stat['correct']/stat['total'], text=f"{topic}: {stat['correct']} / {stat['total']}")
        show_result(record)

elif page == PAGES[5]:
    st.title('Жеке дайындық жоспары')
    if not records:
        st.info('Жоспар үшін алдымен бір тест орындаңыз.')
        st.button('Теориядан бастау', on_click=go, args=(PAGES[1],))
    else:
        minutes = st.select_slider('Күніне дайындалу уақыты', options=[15,20,30,45,60], value=30, format_func=lambda n:f'{n} минут')
        latest = records[0]
        st.caption(f"Негізі: {latest['created'][:19].replace('T',' ')} · {latest.get('title','Бастапқы тест')}. Тек сол тестте қамтылған тақырыптар есепке алынады.")
        st.info('Дұрыс орындалған тапсырма үлесі төмен тақырыптар бірінші келеді. Тең болса, тесттегі реті сақталады. Тақырып саны жетіден көп болса, ең әлсіз жеті тақырып беріледі. Бұл алдын ала оқу ұсынысы.')
        lines = ['AI ҰБТ Mentor — 7 күндік жоспар', '']
        for item in plan(latest['topics'], minutes):
            with st.container(border=True):
                st.markdown(f"### {item['day']}-күн · {item['topic']}")
                st.write(f"{item['minutes']} минут · {item['task']}")
                st.caption('Уақыттың жартысы — теория, жартысы — практика және қате талдау.')
            lines.append(f"{item['day']}-күн: {item['topic']} — {item['minutes']} минут. {item['task']}")
        st.caption('7-күннен кейін қайта тест тапсырып, жаңа жоспар құрыңыз.')
        st.download_button('Жоспарды жүктеу (TXT)', '\n'.join(lines), 'zheke-zhospar.txt', 'text/plain; charset=utf-8')
        st.button('Теория мен тараулық тестке өту', on_click=go, args=(PAGES[1],))
st.divider()
st.caption('AI ҰБТ Mentor 4.0 · Қазақша оқы, түсініп жауап бер, нәтижеңді бақыла.')
