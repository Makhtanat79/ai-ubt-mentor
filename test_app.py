"""Жаңа мазмұнды, бағалауды, сақтауды және оқушы жолдарын тексеру."""
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from streamlit.testing.v1 import AppTest
import mentor_core as core
import mentor_auth as auth

ROOT = Path(__file__).parent
QUESTIONS, CHAPTERS, VARIANTS = core.load_content()
BY_ID = {q['id']:q for q in QUESTIONS}

class ContentTests(unittest.TestCase):
    def test_bank_schema_and_answers(self):
        self.assertEqual(len(BY_ID),620)
        self.assertEqual(len(CHAPTERS),13)
        for q in QUESTIONS:
            with self.subTest(question=q['id']):
                self.assertTrue(q['explanation'])
                self.assertTrue(core.answer_valid(q,q['answer']))
                self.assertEqual(len(q['options']),len(set(q['options'])))
                if q['type']=='multi':
                    self.assertGreaterEqual(len(q['answer']),1)
                    self.assertLess(len(q['answer']),len(q['options']))
        for c in CHAPTERS:
            pool=[q for q in QUESTIONS if q['topic']==c['topic'] and q['type']!='context']
            self.assertEqual(Counter(q['type'] for q in pool),{'single':25,'multi':5,'match':5})
            self.assertTrue(all(c[k] for k in ['theory','example','mistake']))

    def test_all_25_variant_structures(self):
        self.assertEqual(len(VARIANTS),25)
        self.assertEqual(len({tuple(v['question_ids']) for v in VARIANTS}),25)
        for v in VARIANTS:
            quiz=[BY_ID[k] for k in v['question_ids']]
            self.assertEqual(len(set(v['question_ids'])),40)
            self.assertEqual(Counter(q['type'] for q in quiz),{'single':25,'context':5,'multi':5,'match':5})
            self.assertEqual(len({q['context_id'] for q in quiz if q['type']=='context'}),1)
            result=core.grade(quiz,[q['answer'] for q in quiz])
            self.assertEqual((result['score'],result['points'],result['max_points'],result['percent']),(40,50,50,100))
            self.assertEqual(len({q['topic'] for q in quiz if q['type']=='single'}),13)

    def test_all_chapters_have_40_tasks_and_50_points(self):
        tests=json.loads((ROOT/'chapter_tests.json').read_text())
        self.assertEqual(len(tests),13)
        for test in tests:
            quiz=[BY_ID[qid] for qid in test['question_ids']]
            self.assertEqual(len(set(test['question_ids'])),40)
            self.assertTrue(all(q['topic']==test['topic'] for q in quiz))
            self.assertEqual(Counter(q['type'] for q in quiz),{'single':25,'context':5,'multi':5,'match':5})
            self.assertEqual(len({q['context_id'] for q in quiz if q['type']=='context'}),1)
            self.assertEqual(core.grade(quiz,[q['answer'] for q in quiz])['points'],50)
            singles=[q['text'] for q in quiz if q['type']=='single']
            self.assertEqual(len(singles),len(set(singles)))
        html=next(c for c in CHAPTERS if c['topic']=='HTML, CSS және веб-жобалау')
        self.assertIn('<!DOCTYPE html>',html['theory'])
        db=next(c for c in CHAPTERS if c['topic']=='Деректер базасы: кестелер және байланыстар')
        self.assertIn('CREATE TABLE',db['theory'])

    def test_context_calculations_independently(self):
        # Есеп моделі үшін жауапты мәтіндегі санға емес, бастапқы дерекке сүйеніп есептеу.
        for n in range(1,26):
            k=(n-1)//5;typ=(n-1)%5
            qs=[q for q in QUESTIONS if q.get('context_id')==n]
            if typ==0:
                values=[40+2*k,60+2*k,80+2*k,90+2*k]
                expected=[4,sum(values),max(values),sum(x>=80 for x in values),max(values)]
            elif typ==1:
                values=list(range(2+k,7+k))
                expected=[len(values),sum(values),values[-1],values[1],sum(x for x in values if x%2==0)]
            elif typ==2:
                pixels=32*(k+1)*16
                expected=[pixels,pixels,pixels*8,256,pixels*4]
            elif typ==3:
                values=[3+k,7+k,11+k,15+k]
                expected=[sum(values),sum(values)/4,max(values),min(values),4]
            else:
                size=20+4*k
                expected=[size*8,size*2,size,size*4,.5]
            actual=[float(q['options'][q['answer']].replace(',','.')) for q in qs]
            self.assertEqual(actual,expected)

    def test_kazakh_content_no_russian_instruction_phrases(self):
        text=json.dumps([QUESTIONS,CHAPTERS],ensure_ascii=False).lower()
        for phrase in ['выберите','правильный ответ','какой','укажите','соответствие','результат выполнения','сопоставьте']:
            self.assertNotIn(phrase,text)

class MentorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old_db=core.DB
        core.DB=Path(self.temp.name)/'test.db'
        self.user_id=auth.register('оқушы-01','11-сынып','Менің жеке құпия сөзім 2026')
        self.token=auth.login('оқушы-01','Менің жеке құпия сөзім 2026')
        self.profile='account:'+self.user_id

    def tearDown(self):
        core.DB=self.old_db
        self.temp.cleanup()

    def app(self):
        app=AppTest.from_file(str(ROOT/'app.py'))
        app.session_state.auth_token=self.token
        app.run()
        self.assertFalse(app.exception)
        return app

    def nav(self,app,page):
        app.sidebar.radio[0].set_value(page).run()
        self.assertFalse(app.exception)

    def button(self,app,label):
        next(b for b in app.button if b.label==label).click().run()
        self.assertFalse(app.exception)

    def fill_correct(self,app):
        for q in app.session_state['quiz']:
            key=f"ans_{app.session_state['attempt_id']}_{q['id']}"
            if q['type']=='multi':
                app.multiselect(key=key).set_value(q['answer'])
            elif q['type']=='match':
                for j,a in enumerate(q['answer']):
                    app.selectbox(key=f'{key}_{j}').set_value(a)
            else:
                app.radio(key=key).set_value(q['answer'])

    def test_empty_wrong_partial_and_valid_answers(self):
        q=next(q for q in QUESTIONS if q['type']=='multi')
        self.assertFalse(core.answer_complete(q,[]))
        r=core.grade([q],[q['answer'][:1]])
        self.assertEqual(r['points'],0)
        r=core.grade([q],[list(reversed(q['answer']))])
        self.assertEqual(r['points'],2)
        with self.assertRaises(ValueError): core.grade([q],[q['answer']+[q['answer'][0]]])
        with self.assertRaises(ValueError): core.grade([q],[[99]])
        with self.assertRaises(ValueError): core.grade([],[])
        q=next(q for q in QUESTIONS if q['type']=='match')
        self.assertFalse(core.answer_complete(q,[None,0]))
        self.assertEqual(core.grade([q],[[0,0]])['points'],0)
        self.assertEqual(core.grade([q],[q['answer']])['points'],2)
        q=QUESTIONS[0]
        self.assertEqual(core.grade([q],[(q['answer']+1)%len(q['options'])])['score'],0)

    def test_storage_and_legacy(self):
        result=core.grade(QUESTIONS,[q['answer'] for q in QUESTIONS])
        core.save_attempt('same','10A-01',result)
        core.save_attempt('same','10A-01',result)
        self.assertEqual(len(core.history('10A-01')),1)
        self.assertEqual(core.history('10A-02'),[])
        old={'score':1,'total':1,'percent':100,'topics':{'Python':{'correct':1,'total':1}},'details':[{'id':1,'topic':'Python','text':'Бұрынғы сұрақ','options':['1','2'],'answer':0,'selected':0,'correct':True,'explanation':'Түсіндірме'}]}
        core.save_attempt('legacy',self.profile,old)
        app=self.app()
        self.nav(app,'Менің нәтижелерім')
        self.assertEqual(len(app.dataframe),1)
        self.assertTrue(app.success)
        self.nav(app,'Жеке дайындық жоспары')
        self.assertEqual(sum(m.value.startswith('### ') for m in app.markdown),7)

    def test_weak_topic_first(self):
        schedule=core.plan({'Python':{'correct':2,'total':2},'Логика':{'correct':0,'total':2}},20)
        self.assertEqual(schedule[0]['topic'],'Логика')
        self.assertEqual(len(schedule),7)
        self.assertEqual(core.plan({},20),[])

    def test_theory_chapter_full_flow(self):
        app=self.app()
        self.button(app,'Теориядан бастау →')
        self.assertEqual(app.session_state['page'],'Теория және тараулық тест')
        self.assertIn('Шешілген мысал',[s.value for s in app.subheader])
        app.selectbox(key='theory_topic').set_value('Python негіздері').run()
        self.button(app,'Тарау тестін бастау · 40 тапсырма / 50 ұпай')
        self.assertEqual(app.session_state['page'],'Тест тапсыру')
        self.assertEqual(len(app.session_state['quiz']),40)
        self.button(app,'Тестті аяқтау')
        self.assertTrue(app.warning)
        self.assertEqual(core.history(self.profile),[])
        self.fill_correct(app)
        self.button(app,'Тестті аяқтау')
        record=core.history(self.profile)[0]
        self.assertEqual((record['score'],record['points'],record['max_points']),(40,50,50))
        app.run()
        self.assertEqual(len(core.history(self.profile)),1)
        self.nav(app,'Менің нәтижелерім')
        self.assertEqual(len(app.dataframe),1)
        self.nav(app,'Жеке дайындық жоспары')
        self.assertEqual(sum(m.value.startswith('### ') for m in app.markdown),7)
        self.button(app,'Есептік жазбадан шығу')
        self.assertNotIn('quiz',app.session_state)

    def test_variant_complete_repeat_switch_profile(self):
        app=self.app()
        self.nav(app,'ҰБТ-ға дайындық: 25 нұсқа')
        app.selectbox[0].set_value(25).run()
        self.button(app,'Таңдалған нұсқаны бастау')
        quiz_ids=[q['id'] for q in app.session_state['quiz']]
        self.assertEqual(len(quiz_ids),40)
        self.fill_correct(app)
        self.button(app,'Тестті аяқтау')
        record=core.history(self.profile)[0]
        self.assertEqual(record['points'],50)
        self.assertIn('25-нұсқа',record['title'])
        self.button(app,'Таңдалған нұсқаны бастау')
        self.assertEqual(quiz_ids,[q['id'] for q in app.session_state['quiz']])
        self.assertTrue(all(r.value is None for r in app.radio if r.label!='Бөлімдер'))
        self.button(app,'Есептік жазбадан шығу')
        self.assertNotIn('quiz',app.session_state)
        self.nav(app,'Менің нәтижелерім')
        self.assertEqual(len(app.dataframe),0)

    def test_html_and_database_chapters_are_accessible(self):
        app=self.app()
        self.nav(app,'Теория және тараулық тест')
        for topic in ['Деректер базасы: кестелер және байланыстар','Деректер базасы: SQL сұраныстары','HTML, CSS және веб-жобалау']:
            app.selectbox(key='theory_topic').set_value(topic).run()
            self.assertFalse(app.exception)
            self.assertTrue(any(topic in sh.value for sh in app.subheader))
            self.button(app,'Тарау тестін бастау · 40 тапсырма / 50 ұпай')
            self.assertEqual(len(app.session_state['quiz']),40)
            self.assertTrue(all(q['topic']==topic for q in app.session_state['quiz']))
            self.fill_correct(app)
            self.button(app,'Тестті аяқтау')
            self.assertEqual(core.history(self.profile)[0]['points'],50)
            self.nav(app,'Теория және тараулық тест')

    def test_auth_isolation_expiry_and_lockout(self):
        self.assertIsNone(auth.current_user('fake-token'))
        self.assertEqual(auth.current_user(self.token)['profile'],self.profile)
        with core.connect() as con:
            row=con.execute('SELECT password_hash,salt FROM users WHERE id=?',(self.user_id,)).fetchone()
        self.assertNotIn('құпия',row[0])
        self.assertEqual(len(row[0]),64)
        with self.assertRaises(ValueError):auth.register('оқушы-01','11-сынып','Басқа құпия тіркес 2026')
        with self.assertRaises(ValueError):auth.register('new','11-сынып','123')
        for _ in range(5):self.assertIsNone(auth.login('оқушы-01','wrong'))
        self.assertIsNone(auth.login('оқушы-01','Менің жеке құпия сөзім 2026'))
        self.assertIsNotNone(auth.current_user(self.token))
        auth.logout(self.token)
        self.assertIsNone(auth.current_user(self.token))

    def test_guest_gate_registration_login_logout(self):
        app=AppTest.from_file(str(ROOT/'app.py')).run()
        self.assertFalse(app.exception)
        self.nav(app,'Теория және тараулық тест')
        self.assertTrue(app.subheader)
        self.button(app,'Тест үшін кіру немесе тіркелу')
        self.assertIn('Жеке кабинетке кіру',[t.value for t in app.title])
        app.radio(key='auth_form_mode').set_value('Тіркелу').run()
        app.text_input(key='auth_form_username').set_value('жаңа-оқушы')
        app.text_input(key='auth_form_password').set_value('Басқа қауіпсіз тіркес 2026')
        app.text_input(key='auth_form_repeat').set_value('Басқа қауіпсіз тіркес 2026')
        self.button(app,'Тіркелу')
        self.assertNotIn('auth_form_password',app.session_state)
        self.assertIsNotNone(auth.current_user(app.session_state['auth_token']))
        self.button(app,'Жаңа тест бастау')
        self.fill_correct(app)
        self.button(app,'Тестті аяқтау')
        new_profile=auth.current_user(app.session_state['auth_token'])['profile']
        self.assertEqual(len(core.history(new_profile)),1)
        self.assertEqual(core.history(self.profile),[])
        self.button(app,'Есептік жазбадан шығу')
        self.assertNotIn('auth_token',app.session_state)
        self.assertNotIn('result',app.session_state)
        self.nav(app,'Менің нәтижелерім')
        self.assertIn('Жеке кабинетке кіру',[t.value for t in app.title])

    def test_default_practice_is_full_40_question_test(self):
        app=self.app()
        self.nav(app,'Тест тапсыру')
        self.assertEqual(app.radio(key='practice_mode').value,'Толық тест · 40 тапсырма / 50 ұпай')
        self.button(app,'Жаңа тест бастау')
        self.assertEqual(len(app.session_state['quiz']),40)
        self.fill_correct(app)
        self.button(app,'Тестті аяқтау')
        record=core.history(self.profile)[0]
        self.assertEqual(record['max_points'],50)
        self.assertEqual(record['points'],50)

    def test_quick_topic_filter_and_incomplete(self):
        app=self.app()
        self.nav(app,'Тест тапсыру')
        app.radio(key='practice_mode').set_value('Қысқа жаттығу').run()
        app.selectbox[0].set_value('Деректер базасы: SQL сұраныстары').run()
        self.button(app,'Жаңа тест бастау')
        self.assertTrue(all(q['topic']=='Деректер базасы: SQL сұраныстары' for q in app.session_state['quiz']))
        self.button(app,'Тестті аяқтау')
        self.assertTrue(app.warning)
        self.fill_correct(app)
        self.button(app,'Тестті аяқтау')
        self.assertEqual(core.history(self.profile)[0]['percent'],100)

if __name__=='__main__':
    unittest.main()
