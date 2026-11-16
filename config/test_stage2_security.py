"""HTTP経由の認可・CSRF・入力検証。第2.5段階で既知4件を通常テストへ昇格。"""
import json
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, Character, AdminChangeLog, AdminModeAuthorizedUser
from apps.battle.models import Skill, SkillPreset
from apps.chat.models import ChatMessage
from apps.sns.models import Post, Like, Favorite
from apps.inventory.models import Equipment, OwnedEquipment


class SecurityRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=User.objects.create_user(user_id="stage2-security",email="security@example.com",password=None)
        cls.other=User.objects.create_user(user_id="stage2-other",email="other@example.com",password=None)
        cls.empty=User.objects.create_user(user_id="stage2-empty",email="empty@example.com",password=None)
        cls.character=Character.objects.create(user=cls.user,name="投稿者")
        cls.other_character=Character.objects.create(user=cls.other,name="他人")
        cls.post=Post.objects.create(user=cls.other,text="削除禁止")
        cls.owned=OwnedEquipment.objects.create(character=cls.other_character,
            equipment=Equipment.objects.filter(rank="F",slot="weapon").first(),battle_power=10,is_equipped=True)

    def setUp(self): self.client.force_login(self.user)

    def send(self,data,client=None):
        return (client or self.client).post(reverse("chat:send_message"),data=json.dumps(data),content_type="application/json")

    def test_chat_ignores_forged_character_id(self):
        response=self.send({"message":" hello ","character_id":self.other_character.pk})
        self.assertEqual(response.status_code,200)
        message=ChatMessage.objects.get()
        self.assertEqual((message.character_id,message.message),(self.character.pk,"hello"))

    def test_chat_whitespace_is_rejected(self):
        self.assertEqual(self.send({"message":"  \n "}).status_code,400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_chat_length_boundary(self):
        self.assertEqual(self.send({"message":"あ"*200}).status_code,200)
        self.assertEqual(self.send({"message":"あ"*201}).status_code,400)
        self.assertEqual(ChatMessage.objects.count(),1)

    def test_chat_malformed_json(self):
        response=self.client.post(reverse("chat:send_message"),data="{",content_type="application/json")
        self.assertEqual(response.status_code,400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_chat_non_object_json_is_rejected_without_server_error(self):
        for payload in [[], ["message"], None, 1, 1.5, True, False, "message"]:
            with self.subTest(payload=payload):
                response=self.send(payload)
                self.assertEqual(response.status_code,400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_chat_non_string_message_is_rejected(self):
        for value in [None, 1, 1.5, True, False, [], {}]:
            with self.subTest(value=value):
                self.assertEqual(self.send({"message":value}).status_code,400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_chat_invalid_utf8_is_rejected(self):
        response=self.client.post(reverse("chat:send_message"),data=b'\xff',content_type="application/json")
        self.assertEqual(response.status_code,400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_chat_without_character_is_rejected(self):
        self.client.force_login(self.empty)
        self.assertEqual(self.send({"message":"test"}).status_code,400)
        self.assertFalse(ChatMessage.objects.exists())

    def test_chat_get_does_not_send(self):
        self.assertEqual(self.client.get(reverse("chat:send_message")).status_code,405)
        self.assertFalse(ChatMessage.objects.exists())

    def test_chat_messages_reject_post(self):
        self.assertEqual(self.client.post(reverse("chat:get_messages")).status_code,405)

    def test_chat_returns_latest_fifty_in_chronological_order(self):
        for i in range(55): ChatMessage.objects.create(character=self.character,message=str(i))
        response=self.client.get(reverse("chat:get_messages"))
        self.assertEqual([row["message"] for row in response.json()["messages"]],[str(i) for i in range(5,55)])

    def test_anonymous_mutations_require_login(self):
        anonymous=Client()
        for name,args,data in [
            ("mini_create_post",[],{"text":"bad"}), ("toggle_like",[self.post.pk],{}),
            ("delete_post",[self.post.pk],{}), ("shop:buy_item",[999],{}),
            ("shop:buy_market_listing",[999],{}), ("inventory:equip_equipment",[self.owned.pk],{}),
            ("admin_player_edit",[self.character.pk],{"gold":999}),
        ]:
            with self.subTest(name=name):
                response=anonymous.post(reverse(name,args=args),data)
                self.assertEqual(response.status_code,302)
        self.assertEqual(self.send({"message":"bad"},anonymous).status_code,302)
        self.assertEqual(Post.objects.count(),1)
        self.assertFalse(ChatMessage.objects.exists())

    def test_other_users_post_cannot_be_deleted(self):
        response=self.client.post(reverse("delete_post",args=[self.post.pk]))
        self.assertEqual(response.status_code,404)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_owner_delete_requires_post(self):
        self.client.force_login(self.other)
        url=reverse("delete_post",args=[self.post.pk])
        self.client.get(url)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        self.client.post(url)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_sns_ignores_forged_author(self):
        response=self.client.post(reverse("mini_create_post"),{"text":"new","user":self.other.pk})
        self.assertEqual(response.status_code,200)
        self.assertEqual(Post.objects.get(text="new").user_id,self.user.pk)

    def test_sns_invalid_post_does_not_create_record(self):
        for text in ["","x"*181]:
            self.assertEqual(self.client.post(reverse("mini_create_post"),{"text":text}).status_code,400)
        self.assertEqual(Post.objects.count(),1)

    def test_like_toggle_preserves_uniqueness(self):
        url=reverse("toggle_like",args=[self.post.pk])
        self.assertTrue(self.client.post(url).json()["liked"])
        self.assertFalse(self.client.post(url).json()["liked"])
        self.assertTrue(self.client.post(url).json()["liked"])
        self.assertEqual(Like.objects.filter(post=self.post,user=self.user).count(),1)

    def test_favorite_toggle_preserves_uniqueness(self):
        url=reverse("toggle_favorite",args=[self.post.pk])
        self.client.post(url);self.client.post(url);self.client.post(url)
        self.assertEqual(Favorite.objects.filter(post=self.post,user=self.user).count(),1)

    def test_sns_admin_without_mode_is_rejected(self):
        self.assertEqual(self.client.post(reverse("admin_delete_post",args=[self.post.pk])).status_code,403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        self.assertFalse(AdminChangeLog.objects.exists())

    def test_sns_admin_requires_authorization_record_even_with_session(self):
        like=Like.objects.create(user=self.user,post=self.post)
        favorite=Favorite.objects.create(user=self.user,post=self.post)
        session=self.client.session;session["admin_mode"]=True;session.save()
        response=self.client.post(reverse("admin_delete_post",args=[self.post.pk]))
        self.assertEqual(response.status_code,403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        self.assertTrue(Like.objects.filter(pk=like.pk).exists())
        self.assertTrue(Favorite.objects.filter(pk=favorite.pk).exists())
        self.assertFalse(AdminChangeLog.objects.exists())

    def test_authorized_admin_can_delete_and_create_audit_log(self):
        AdminModeAuthorizedUser.objects.create(user=self.user)
        session=self.client.session;session["admin_mode"]=True;session.save()
        Like.objects.create(user=self.user,post=self.post)
        Favorite.objects.create(user=self.user,post=self.post)
        response=self.client.post(reverse("admin_delete_post",args=[self.post.pk]))
        self.assertRedirects(response,reverse("admin_panel"),fetch_redirect_response=False)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())
        self.assertFalse(Like.objects.exists())
        self.assertFalse(Favorite.objects.exists())
        log=AdminChangeLog.objects.get(action_type="sns_post_delete")
        self.assertEqual(log.user_id,self.user.pk)
        self.assertEqual(log.target_character_id,self.other_character.pk)
        self.assertEqual(log.changes["post_id"]["before"],self.post.pk)

    def test_authorized_user_without_active_mode_cannot_delete(self):
        AdminModeAuthorizedUser.objects.create(user=self.user)
        response=self.client.post(reverse("admin_delete_post",args=[self.post.pk]))
        self.assertEqual(response.status_code,403)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        self.assertFalse(AdminChangeLog.objects.exists())

    def test_authorized_admin_get_does_not_delete(self):
        AdminModeAuthorizedUser.objects.create(user=self.user)
        session=self.client.session;session["admin_mode"]=True;session.save()
        response=self.client.get(reverse("admin_delete_post",args=[self.post.pk]))
        self.assertEqual(response.status_code,405)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())
        self.assertFalse(AdminChangeLog.objects.exists())

    def test_like_get_must_not_mutate_database(self):
        response=self.client.get(reverse("toggle_like",args=[self.post.pk]))
        self.assertEqual(response.status_code,405)
        self.assertFalse(Like.objects.filter(post=self.post,user=self.user).exists())

    def test_favorite_get_must_not_mutate_database(self):
        response=self.client.get(reverse("toggle_favorite",args=[self.post.pk]))
        self.assertEqual(response.status_code,405)
        self.assertFalse(Favorite.objects.filter(post=self.post,user=self.user).exists())

    def test_rejected_methods_preserve_existing_like_and_favorite(self):
        like=Like.objects.create(user=self.user,post=self.post)
        favorite=Favorite.objects.create(user=self.user,post=self.post)
        for name in ["toggle_like","toggle_favorite"]:
            for method in ["get","head","put","patch","delete"]:
                with self.subTest(name=name,method=method):
                    response=getattr(self.client,method)(reverse(name,args=[self.post.pk]))
                    self.assertEqual(response.status_code,405)
                    self.assertTrue(Like.objects.filter(pk=like.pk).exists())
                    self.assertTrue(Favorite.objects.filter(pk=favorite.pk).exists())

    def test_sns_post_toggles_with_valid_csrf_token(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.user)
        strict.get(reverse("home"))
        token=strict.cookies["csrftoken"].value
        url=reverse("toggle_like",args=[self.post.pk])
        first=strict.post(url,HTTP_X_CSRFTOKEN=token)
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.json(),{"liked":True,"like_count":1})
        self.assertEqual(strict.post(url,HTTP_X_CSRFTOKEN=token).json(),{"liked":False,"like_count":0})
        url=reverse("toggle_favorite",args=[self.post.pk])
        self.assertEqual(strict.post(url,HTTP_X_CSRFTOKEN=token).json(),{"favorited":True})
        self.assertEqual(strict.post(url,HTTP_X_CSRFTOKEN=token).json(),{"favorited":False})

    def test_csrf_missing_token_rejects_authenticated_mutations(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.user)
        for name,args,data in [
            ("mini_create_post",[],{"text":"bad"}), ("toggle_like",[self.post.pk],{}),
            ("toggle_favorite",[self.post.pk],{}),
            ("admin_delete_post",[self.post.pk],{}),
            ("delete_post",[self.post.pk],{}), ("shop:buy_item",[999],{}),
            ("inventory:equip_equipment",[self.owned.pk],{}),
            ("admin_player_edit",[self.character.pk],{"gold":999}),
        ]:
            with self.subTest(name=name): self.assertEqual(strict.post(reverse(name,args=args),data).status_code,403)
        self.assertEqual(self.send({"message":"bad"},strict).status_code,403)
        self.assertFalse(ChatMessage.objects.exists());self.assertEqual(Post.objects.count(),1)

    def test_chat_valid_csrf_token_succeeds(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.user)
        strict.get(reverse("home"))
        token=strict.cookies["csrftoken"].value
        response=strict.post(reverse("chat:send_message"),data=json.dumps({"message":"safe"}),
            content_type="application/json",HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(ChatMessage.objects.get().character_id,self.character.pk)

    def test_tactics_rejects_other_job_without_losing_old_preset(self):
        skill=Skill.objects.filter(job="wanderer",is_passive=False).first()
        foreign=Skill.objects.filter(job="wizard").first()
        preset=SkillPreset.objects.create(character=self.character,skill=skill,slot=1,use_count=3)
        response=self.client.post(reverse("battle:tactics"),{"skill_1":foreign.pk,"use_count_1":99})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context["error_message"])
        preset.refresh_from_db();self.assertEqual((preset.skill_id,preset.use_count),(skill.pk,3))

    def test_equipping_others_equipment_is_rejected(self):
        for action in ["equip_equipment","unequip_equipment"]:
            with self.subTest(action=action):
                response=self.client.post(reverse("inventory:"+action,args=[self.owned.pk]))
                self.assertEqual(response.status_code,404)
                self.owned.refresh_from_db()
                self.assertEqual(self.owned.character_id,self.other_character.pk)
                self.assertTrue(self.owned.is_equipped)
