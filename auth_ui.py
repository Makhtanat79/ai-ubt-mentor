"""Қазақша тіркелу және кіру пішіндері."""
import sqlite3
import streamlit as st
import mentor_auth as auth


def clear_private_state():
    for key in list(st.session_state):
        if key != 'page':
            del st.session_state[key]


def sign_out():
    auth.logout(st.session_state.get('auth_token'))
    clear_private_state()
    st.session_state.page = 'Басты бет'


def user_from_session():
    if st.session_state.pop('_clear_auth_forms', False):
        for key in list(st.session_state):
            if key.startswith('auth_form_'):
                del st.session_state[key]
    return auth.current_user(st.session_state.get('auth_token'))


def render_auth():
    st.title('Жеке кабинетке кіру')
    st.write('Теория тіркелмей ашылады. Тест, жеке нәтиже және жоспар үшін кіріңіз.')
    st.caption('Аты-жөніңізді, телефонды немесе электрондық поштаны сұрамаймыз. Бүркеншік ат қолданыңыз. Құпиясөзді сақтап алыңыз: автоматты қалпына келтіру әзірге жоқ.')
    mode = st.radio('Есептік жазба', ['Кіру', 'Тіркелу'], horizontal=True, key='auth_form_mode')
    with st.form('auth_form', clear_on_submit=False):
        username = st.text_input('Пайдаланушы аты', max_chars=32, key='auth_form_username')
        password = st.text_input('Құпиясөз', type='password', max_chars=128, key='auth_form_password')
        if mode == 'Тіркелу':
            school_class = st.selectbox('Сыныбыңыз', ['10-сынып', '11-сынып'])
            repeat = st.text_input('Құпиясөзді қайталаңыз', type='password', max_chars=128, key='auth_form_repeat')
            st.caption('Кемінде 12 таңба. Мысалы, есіңізде қалатын бірнеше сөзден тұратын жеке тіркес таңдаңыз.')
        submitted = st.form_submit_button('Тіркелу' if mode == 'Тіркелу' else 'Кіру', type='primary')
    if not submitted:
        return
    try:
        if mode == 'Тіркелу':
            if password != repeat:
                st.error('Екі құпиясөз сәйкес келмейді.')
                return
            auth.register(username, school_class, password)
        token = auth.login(username, password)
        if token:
            st.session_state.auth_token = token
            st.session_state._clear_auth_forms = True
            st.rerun()
        else:
            st.error('Кіру орындалмады. Деректерді тексеріңіз. Бірнеше сәтсіз әрекеттен кейін 15 минут күтіп көріңіз.')
    except ValueError as error:
        st.error(str(error))
    except (sqlite3.Error, OSError):
        st.error('Есептік жазбаны сақтау мүмкін болмады. Деректер қалтасының рұқсатын тексеріңіз.')
