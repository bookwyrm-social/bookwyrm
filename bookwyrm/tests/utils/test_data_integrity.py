"""Tests for data integrity checking utilities"""

from unittest.mock import patch
from django.test import TestCase
from bookwyrm import models
from bookwyrm.utils.data_integrity import DataIntegrityChecker


class DataIntegrityCheckerOrphanedTest(TestCase):
    """Test orphaned data detection"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.user = models.User.objects.create_user(
                "test@example.com",
                "test@test.com",
                "password",
                local=True,
                localname="testuser",
            )

    def setUp(self):
        """Set up test fixtures"""
        self.checker = DataIntegrityChecker()

    def test_check_orphaned_statuses_none(self):
        """No orphaned statuses when user exists"""
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(
                user=self.user,
                content="Test status",
            )

        issues = self.checker.check_orphaned_statuses()
        
        self.assertEqual(len(issues), 0)

    def test_check_orphaned_statuses_found(self):
        """Detect orphaned statuses"""
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            status = models.Status.objects.create(
                user=self.user,
                content="Test status",
            )
        
        # Simulate orphaned status by deleting user
        status.user = None
        status.save()

        issues = self.checker.check_orphaned_statuses()
        
        self.assertGreater(len(issues), 0)
        self.assertEqual(issues[0]["model"], "Status")

    def test_check_orphaned_reviews_none(self):
        """No orphaned reviews when book and user exist"""
        work = models.Work.objects.create(title="Test Work")
        book = models.Edition.objects.create(
            title="Test Book",
            parent_work=work,
        )
        
        with patch("bookwyrm.activitystreams.add_status_task.delay"):
            review = models.Review.objects.create(
                user=self.user,
                book=book,
                content="Great book!",
                rating=5.0,
            )

        issues = self.checker.check_orphaned_reviews()
        
        self.assertEqual(len(issues), 0)

    def test_check_orphaned_shelf_books_none(self):
        """No orphaned shelf books"""
        work = models.Work.objects.create(title="Test Work")
        book = models.Edition.objects.create(
            title="Test Book",
            parent_work=work,
        )
        shelf = models.Shelf.objects.create(
            user=self.user,
            name="To Read",
        )
        shelf_book = models.ShelfBook.objects.create(
            user=self.user,
            shelf=shelf,
            book=book,
        )

        issues = self.checker.check_orphaned_shelf_books()
        
        self.assertEqual(len(issues), 0)

    def test_check_orphaned_list_items_none(self):
        """No orphaned list items"""
        work = models.Work.objects.create(title="Test Work")
        book = models.Edition.objects.create(
            title="Test Book",
            parent_work=work,
        )
        book_list = models.List.objects.create(
            user=self.user,
            name="My List",
        )
        list_item = models.ListItem.objects.create(
            book_list=book_list,
            user=self.user,
            book=book,
            order=1,
        )

        issues = self.checker.check_orphaned_list_items()
        
        self.assertEqual(len(issues), 0)


class DataIntegrityCheckerRelationshipsTest(TestCase):
    """Test relationship integrity"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.user1 = models.User.objects.create_user(
                "user1@example.com",
                "user1@test.com",
                "password",
                local=True,
                localname="user1",
            )
            cls.user2 = models.User.objects.create_user(
                "user2@example.com",
                "user2@test.com",
                "password",
                local=True,
                localname="user2",
            )

    def setUp(self):
        """Set up test fixtures"""
        self.checker = DataIntegrityChecker()

    def test_check_user_relationships_valid(self):
        """Valid user relationships"""
        # Create valid follow relationship
        models.UserFollows.objects.create(
            user_subject=self.user1,
            user_object=self.user2,
        )

        issues = self.checker.check_user_relationships()
        
        # Should have no self-follows or duplicate follows
        self_follows = [i for i in issues if "self-follow" in i["description"].lower()]
        self.assertEqual(len(self_follows), 0)

    def test_check_user_relationships_self_follow(self):
        """Detect self-follow relationships"""
        # Create self-follow
        models.UserFollows.objects.create(
            user_subject=self.user1,
            user_object=self.user1,
        )

        issues = self.checker.check_user_relationships()
        
        self_follows = [i for i in issues if "self-follow" in i["description"].lower()]
        self.assertGreater(len(self_follows), 0)

    def test_check_user_relationships_duplicates(self):
        """Detect duplicate follow relationships"""
        # Create duplicate follows
        models.UserFollows.objects.create(
            user_subject=self.user1,
            user_object=self.user2,
        )
        models.UserFollows.objects.create(
            user_subject=self.user1,
            user_object=self.user2,
        )

        issues = self.checker.check_user_relationships()
        
        duplicates = [i for i in issues if "duplicate" in i["description"].lower()]
        self.assertGreater(len(duplicates), 0)


class DataIntegrityCheckerBookRelationshipsTest(TestCase):
    """Test book relationship integrity"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = DataIntegrityChecker()

    def test_check_book_relationships_valid(self):
        """Valid book relationships"""
        work = models.Work.objects.create(title="Test Work")
        author = models.Author.objects.create(name="Test Author")
        book = models.Edition.objects.create(
            title="Test Book",
            parent_work=work,
        )
        book.authors.add(author)

        issues = self.checker.check_book_relationships()
        
        # No issues for valid book
        orphaned_editions = [i for i in issues if "without work" in i["description"].lower()]
        self.assertEqual(len(orphaned_editions), 0)

    def test_check_book_relationships_no_work(self):
        """Detect books without parent work"""
        book = models.Edition.objects.create(
            title="Orphaned Book",
            parent_work=None,
        )

        issues = self.checker.check_book_relationships()
        
        no_work_issues = [i for i in issues if "without work" in i["description"].lower()]
        self.assertGreater(len(no_work_issues), 0)

    def test_check_book_relationships_no_authors(self):
        """Detect books without authors"""
        work = models.Work.objects.create(title="Test Work")
        book = models.Edition.objects.create(
            title="Book Without Author",
            parent_work=work,
        )

        issues = self.checker.check_book_relationships()
        
        no_author_issues = [i for i in issues if "without author" in i["description"].lower()]
        self.assertGreater(len(no_author_issues), 0)


class DataIntegrityCheckerFederationTest(TestCase):
    """Test federation data integrity"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.local_user = models.User.objects.create_user(
                "local@example.com",
                "local@test.com",
                "password",
                local=True,
                localname="localuser",
            )

    def setUp(self):
        """Set up test fixtures"""
        self.checker = DataIntegrityChecker()

    def test_check_federation_data_valid_remote_user(self):
        """Valid remote user with server"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            server = models.FederatedServer.objects.create(
                server_name="remote.example.com"
            )
            remote_user = models.User.objects.create_user(
                "remote@remote.example.com",
                "remote@remote.com",
                "password",
                local=False,
                localname="remoteuser",
                federated_server=server,
                remote_id="https://remote.example.com/users/remoteuser",
            )

        issues = self.checker.check_federation_data()
        
        # Should have no issues for valid remote user
        remote_user_issues = [i for i in issues if remote_user.username in str(i)]
        self.assertEqual(len(remote_user_issues), 0)

    def test_check_federation_data_local_user_skipped(self):
        """Local users are skipped"""
        issues = self.checker.check_federation_data()
        
        # Local user should not appear in federation issues
        local_user_issues = [i for i in issues if self.local_user.username in str(i)]
        self.assertEqual(len(local_user_issues), 0)

    def test_check_federation_data_missing_remote_id(self):
        """Detect remote users with invalid remote_id"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            server = models.FederatedServer.objects.create(
                server_name="remote.example.com"
            )
            remote_user = models.User.objects.create_user(
                "badremote@remote.example.com",
                "badremote@remote.com",
                "password",
                local=False,
                localname="badremote",
                federated_server=server,
                remote_id="",  # Invalid remote_id
            )

        issues = self.checker.check_federation_data()
        
        remote_id_issues = [i for i in issues if "remote_id" in i["description"].lower()]
        self.assertGreater(len(remote_id_issues), 0)


class DataIntegrityCheckerDuplicatesTest(TestCase):
    """Test duplicate record detection"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.user = models.User.objects.create_user(
                "test@example.com",
                "test@test.com",
                "password",
                local=True,
                localname="testuser",
            )

    def setUp(self):
        """Set up test fixtures"""
        self.checker = DataIntegrityChecker()

    def test_find_duplicate_records_none(self):
        """No duplicates found"""
        work1 = models.Work.objects.create(title="Unique Work 1")
        work2 = models.Work.objects.create(title="Unique Work 2")

        duplicates = self.checker.find_duplicate_records(models.Work, "title")
        
        self.assertEqual(len(duplicates), 0)

    def test_find_duplicate_records_found(self):
        """Find duplicate records"""
        work1 = models.Work.objects.create(title="Duplicate Work")
        work2 = models.Work.objects.create(title="Duplicate Work")

        duplicates = self.checker.find_duplicate_records(models.Work, "title")
        
        self.assertGreater(len(duplicates), 0)
        self.assertEqual(duplicates[0]["field_value"], "Duplicate Work")
        self.assertGreaterEqual(duplicates[0]["count"], 2)


class DataIntegrityCheckerForeignKeysTest(TestCase):
    """Test foreign key validation"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.user = models.User.objects.create_user(
                "test@example.com",
                "test@test.com",
                "password",
                local=True,
                localname="testuser",
            )

    def setUp(self):
        """Set up test fixtures"""
        self.checker = DataIntegrityChecker()

    def test_validate_foreign_keys_valid(self):
        """No NULL foreign keys"""
        work = models.Work.objects.create(title="Test Work")
        book = models.Edition.objects.create(
            title="Test Book",
            parent_work=work,
        )

        issues = self.checker.validate_foreign_keys(models.Edition, ["parent_work"])
        
        self.assertEqual(len(issues), 0)

    def test_validate_foreign_keys_null(self):
        """Detect NULL foreign keys"""
        book = models.Edition.objects.create(
            title="Book Without Work",
            parent_work=None,
        )

        issues = self.checker.validate_foreign_keys(models.Edition, ["parent_work"])
        
        self.assertGreater(len(issues), 0)
        self.assertEqual(issues[0]["model"], "Edition")
        self.assertEqual(issues[0]["field"], "parent_work")


class DataIntegrityCheckerIntegrationTest(TestCase):
    """Integration tests for data integrity checker"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        with (
            patch("bookwyrm.suggested_users.rerank_suggestions_task.delay"),
            patch("bookwyrm.activitystreams.populate_stream_task.delay"),
            patch("bookwyrm.lists_stream.populate_lists_task.delay"),
        ):
            cls.user = models.User.objects.create_user(
                "test@example.com",
                "test@test.com",
                "password",
                local=True,
                localname="testuser",
            )

    def setUp(self):
        """Set up test fixtures"""
        self.checker = DataIntegrityChecker()

    def test_comprehensive_integrity_check(self):
        """Run comprehensive integrity checks"""
        # Create valid data
        work = models.Work.objects.create(title="Test Work")
        author = models.Author.objects.create(name="Test Author")
        book = models.Edition.objects.create(
            title="Test Book",
            parent_work=work,
        )
        book.authors.add(author)

        # Run all checks
        orphaned_statuses = self.checker.check_orphaned_statuses()
        orphaned_reviews = self.checker.check_orphaned_reviews()
        user_relationships = self.checker.check_user_relationships()
        book_relationships = self.checker.check_book_relationships()
        
        # Valid data should have no issues
        total_issues = (
            len(orphaned_statuses) +
            len(orphaned_reviews) +
            len(user_relationships) +
            len(book_relationships)
        )
        
        self.assertEqual(total_issues, 0)

    def test_multiple_integrity_issues(self):
        """Detect multiple integrity issues"""
        # Create invalid data
        book_no_work = models.Edition.objects.create(
            title="Book Without Work",
            parent_work=None,
        )
        
        book_no_author = models.Edition.objects.create(
            title="Book Without Author",
            parent_work=models.Work.objects.create(title="Work"),
        )
        
        # Check book relationships
        issues = self.checker.check_book_relationships()
        
        # Should detect multiple issues
        self.assertGreaterEqual(len(issues), 2)


class DataIntegrityCheckerErrorHandlingTest(TestCase):
    """Test error handling in data integrity checker"""

    def setUp(self):
        """Set up test fixtures"""
        self.checker = DataIntegrityChecker()

    @patch("bookwyrm.utils.data_integrity.models.Status.objects.filter")
    def test_check_orphaned_statuses_error(self, mock_filter):
        """Handle errors in orphaned status check"""
        mock_filter.side_effect = Exception("Database error")

        issues = self.checker.check_orphaned_statuses()
        
        # Should return empty list on error
        self.assertEqual(len(issues), 0)

    def test_find_duplicate_records_invalid_model(self):
        """Handle invalid model in duplicate check"""
        # Should not raise exception
        duplicates = self.checker.find_duplicate_records(None, "field")
        
        self.assertEqual(len(duplicates), 0)

    def test_validate_foreign_keys_invalid_field(self):
        """Handle invalid field in foreign key check"""
        # Should not raise exception
        issues = self.checker.validate_foreign_keys(models.Work, ["nonexistent_field"])
        
        self.assertEqual(len(issues), 0)
