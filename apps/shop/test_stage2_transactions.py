"""通貨・在庫の保存則、所有権、二重送信、例外時ロールバック。"""
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import User, Character
from apps.inventory.models import Item, InventoryItem, Equipment, OwnedEquipment
from apps.shop.models import ShopStock, MarketListing, MarketSaleNotification


class TransactionRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer_user=User.objects.create_user(user_id="stage2-buyer",email="buyer-stage2@example.com",password=None)
        cls.seller_user=User.objects.create_user(user_id="stage2-seller",email="seller-stage2@example.com",password=None)
        cls.buyer=Character.objects.create(user=cls.buyer_user,name="購入者",gold=1000)
        cls.seller=Character.objects.create(user=cls.seller_user,name="出品者",gold=100)
        cls.item=Item.objects.create(name="取引素材",category="material",buy_price=10,
            market_sellable=True,npc_purchasable=True)
        cls.inventory=InventoryItem.objects.create(character=cls.seller,item=cls.item,quantity=10)
        cls.stock=ShopStock.objects.create(item=cls.item,stock=2)
        cls.master=Equipment.objects.filter(rank="F",slot="weapon").first()
        cls.owned=OwnedEquipment.objects.create(character=cls.seller,equipment=cls.master,
            battle_power=cls.master.base_battle_power,enhancement_level=0)

    def setUp(self): self.client.force_login(self.buyer_user)

    def listing(self,equipment=False):
        self.client.force_login(self.seller_user)
        url=reverse("shop:create_equipment_listing",args=[self.owned.pk]) if equipment else reverse("shop:create_market_listing",args=[self.inventory.pk])
        response=self.client.post(url,{"quantity":3,"unit_price":20})
        self.assertEqual(response.status_code,302)
        return MarketListing.objects.get(seller=self.seller)

    def purchase(self,listing,quantity=None):
        self.client.force_login(self.buyer_user)
        data={} if quantity is None else {"quantity":quantity}
        return self.client.post(reverse("shop:buy_market_listing",args=[listing.pk]),data)

    def assert_balances(self,buyer=1000,seller=100):
        self.buyer.refresh_from_db();self.seller.refresh_from_db()
        self.assertEqual((self.buyer.gold,self.seller.gold),(buyer,seller))

    def test_material_sale_conserves_quantity_and_money(self):
        listing=self.listing()
        # 数量未指定は1個購入。残り2個を明示購入し、総数量/Qの保存も確認する。
        self.purchase(listing)
        self.assert_balances(980,120)
        listing.refresh_from_db()
        self.inventory.refresh_from_db()
        self.assertEqual((self.inventory.quantity,listing.quantity),(7,2))
        self.assertEqual(InventoryItem.objects.get(character=self.buyer,item=self.item).quantity,1)
        self.assertEqual(listing.status,MarketListing.Status.LISTED)
        self.assertIsNone(listing.buyer_id)
        self.assertEqual(MarketSaleNotification.objects.filter(recipient=self.seller,listing=listing).count(),1)
        self.purchase(listing,quantity=2)
        self.assert_balances(940,160)
        self.inventory.refresh_from_db();listing.refresh_from_db()
        self.assertEqual(self.inventory.quantity,7)
        self.assertEqual(listing.quantity,0)
        self.assertEqual(InventoryItem.objects.get(character=self.buyer,item=self.item).quantity,3)
        self.assertEqual(listing.status,MarketListing.Status.SOLD)
        self.assertEqual(listing.buyer_id,self.buyer.pk)
        self.assertEqual(MarketSaleNotification.objects.filter(recipient=self.seller,listing=listing).count(),2)

    def test_repeat_purchase_is_not_charged_or_granted_twice(self):
        listing=self.listing();self.purchase(listing,quantity=3);self.purchase(listing,quantity=3)
        self.assert_balances(940,160)
        self.assertEqual(InventoryItem.objects.get(character=self.buyer,item=self.item).quantity,3)
        self.assertEqual(MarketSaleNotification.objects.count(),1)
        listing.refresh_from_db();self.inventory.refresh_from_db()
        self.assertEqual((listing.quantity,self.inventory.quantity),(0,7))
        self.assertEqual(listing.status,MarketListing.Status.SOLD)
        self.assertEqual(listing.buyer_id,self.buyer.pk)

    def test_self_purchase_is_rejected(self):
        listing=self.listing()
        self.client.post(reverse("shop:buy_market_listing",args=[listing.pk]))
        self.assert_balances()
        listing.refresh_from_db();self.assertEqual(listing.status,MarketListing.Status.LISTED)

    def test_insufficient_money_does_not_mutate_listing(self):
        listing=self.listing()
        Character.objects.filter(pk=self.buyer.pk).update(gold=59)
        self.purchase(listing,quantity=3);self.assert_balances(59,100)
        self.assertFalse(InventoryItem.objects.filter(character=self.buyer).exists())
        listing.refresh_from_db();self.assertEqual(listing.status,MarketListing.Status.LISTED)
        self.inventory.refresh_from_db()
        self.assertEqual((listing.quantity,self.inventory.quantity),(3,7))
        self.assertIsNone(listing.buyer_id)
        self.assertFalse(MarketSaleNotification.objects.exists())

    def test_cancel_returns_stock_once(self):
        listing=self.listing()
        url=reverse("shop:cancel_market_listing",args=[listing.pk])
        self.client.post(url);self.client.post(url)
        self.inventory.refresh_from_db();listing.refresh_from_db()
        self.assertEqual(self.inventory.quantity,10)
        self.assertEqual(listing.status,MarketListing.Status.CANCELLED)

    def test_cancelled_listing_cannot_be_purchased(self):
        listing=self.listing()
        self.client.post(reverse("shop:cancel_market_listing",args=[listing.pk]))
        self.purchase(listing);self.assert_balances()
        self.assertFalse(InventoryItem.objects.filter(character=self.buyer).exists())

    def test_other_user_cannot_cancel(self):
        listing=self.listing();self.client.force_login(self.buyer_user)
        self.client.post(reverse("shop:cancel_market_listing",args=[listing.pk]))
        listing.refresh_from_db();self.inventory.refresh_from_db()
        self.assertEqual(listing.status,MarketListing.Status.LISTED)
        self.assertEqual(self.inventory.quantity,7)

    def test_other_user_cannot_list_material(self):
        self.client.post(reverse("shop:create_market_listing",args=[self.inventory.pk]),{"quantity":1,"unit_price":1})
        self.inventory.refresh_from_db();self.assertEqual(self.inventory.quantity,10)
        self.assertFalse(MarketListing.objects.exists())

    def test_equipment_sale_transfers_same_instance_and_stats(self):
        listing=self.listing(True);self.purchase(listing)
        self.owned.refresh_from_db()
        self.assertEqual(self.owned.character_id,self.buyer.pk)
        self.assertEqual(self.owned.battle_power,self.master.base_battle_power)
        self.assertFalse(self.owned.is_equipped)
        self.assert_balances(980,120)

    def test_equipment_cannot_be_listed_twice(self):
        self.listing(True)
        self.client.post(reverse("shop:create_equipment_listing",args=[self.owned.pk]),{"unit_price":99})
        self.assertEqual(MarketListing.objects.count(),1)

    def test_other_user_cannot_list_equipment(self):
        self.client.post(reverse("shop:create_equipment_listing",args=[self.owned.pk]),{"unit_price":1})
        self.owned.refresh_from_db();self.assertEqual(self.owned.character_id,self.seller.pk)
        self.assertFalse(MarketListing.objects.exists())

    def test_equipped_item_cannot_be_listed(self):
        self.owned.is_equipped=True;self.owned.save()
        self.client.force_login(self.seller_user)
        self.client.post(reverse("shop:create_equipment_listing",args=[self.owned.pk]),{"unit_price":1})
        self.assertFalse(MarketListing.objects.exists())

    def test_notification_failure_rolls_back_entire_sale(self):
        listing=self.listing()
        with patch("apps.shop.views.MarketSaleNotification.objects.create",side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError): self.purchase(listing)
        self.assert_balances()
        listing.refresh_from_db();self.assertEqual(listing.status,MarketListing.Status.LISTED)
        self.assertIsNone(listing.buyer_id)
        self.assertFalse(InventoryItem.objects.filter(character=self.buyer).exists())

    def test_listing_failure_keeps_inventory(self):
        self.client.force_login(self.seller_user)
        with patch("apps.shop.views.MarketListing.objects.create",side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("shop:create_market_listing",args=[self.inventory.pk]),{"quantity":2,"unit_price":10})
        self.inventory.refresh_from_db();self.assertEqual(self.inventory.quantity,10)
        self.assertFalse(MarketListing.objects.exists())

    def test_npc_sale_uses_price_and_stock(self):
        self.stock.sale_price=25;self.stock.save()
        self.client.post(reverse("shop:buy_item",args=[self.stock.pk]))
        self.buyer.refresh_from_db();self.stock.refresh_from_db()
        self.assertEqual((self.buyer.gold,self.stock.stock),(975,1))
        self.assertEqual(InventoryItem.objects.get(character=self.buyer,item=self.item).quantity,1)

    def test_npc_sold_out_cannot_duplicate_item(self):
        self.stock.stock=1;self.stock.save()
        url=reverse("shop:buy_item",args=[self.stock.pk])
        self.client.post(url);self.client.post(url)
        self.buyer.refresh_from_db();self.stock.refresh_from_db()
        self.assertEqual((self.buyer.gold,self.stock.stock),(990,0))
        self.assertEqual(InventoryItem.objects.get(character=self.buyer,item=self.item).quantity,1)

    def test_npc_failure_rolls_back_money_and_stock(self):
        with patch("apps.shop.views.InventoryItem.objects.get_or_create",side_effect=RuntimeError("test")):
            with self.assertRaises(RuntimeError): self.client.post(reverse("shop:buy_item",args=[self.stock.pk]))
        self.stock.refresh_from_db();self.assertEqual(self.stock.stock,2)
        self.assert_balances()


def invalid_listing(self,case):
    quantity,price=case
    self.client.force_login(self.seller_user)
    self.client.post(reverse("shop:create_market_listing",args=[self.inventory.pk]),{"quantity":quantity,"unit_price":price})
    self.inventory.refresh_from_db();self.assertEqual(self.inventory.quantity,10)
    self.assertFalse(MarketListing.objects.exists());self.assert_balances()


for label,case in {"zero_quantity":(0,10),"negative_quantity":(-1,10),"excess_quantity":(11,10),
                   "non_numeric":("x",10),"zero_price":(1,0),"negative_price":(1,-1)}.items():
    def test(self,case=case): invalid_listing(self,case)
    setattr(TransactionRegressionTests,"test_listing_rejects_"+label,test)


def unavailable_npc(self,reason):
    if reason=="disabled": self.stock.is_available=False;self.stock.save()
    if reason=="not_purchasable": self.item.npc_purchasable=False;self.item.save()
    if reason=="equipment": self.item.category="equipment";self.item.save()
    if reason=="insufficient": Character.objects.filter(pk=self.buyer.pk).update(gold=9)
    if reason=="get": response=self.client.get(reverse("shop:buy_item",args=[self.stock.pk]))
    else: response=self.client.post(reverse("shop:buy_item",args=[self.stock.pk]))
    self.assertEqual(response.status_code,302)
    self.stock.refresh_from_db();self.assertEqual(self.stock.stock,2)
    self.assertFalse(InventoryItem.objects.filter(character=self.buyer).exists())
    self.assert_balances(9 if reason=="insufficient" else 1000,100)


for reason in ["disabled","not_purchasable","equipment","insufficient","get"]:
    def test(self,reason=reason): unavailable_npc(self,reason)
    setattr(TransactionRegressionTests,"test_npc_rejects_"+reason,test)
