# Copyright 2017 New Vector Ltd
# Copyright 2019 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import logging
from typing import TYPE_CHECKING, Any, Collection, Dict, List, Optional, Tuple, Union

from synapse.rest.media.v1._base import FileInfo
from synapse.rest.media.v1.media_storage import ReadableFileWrapper
from synapse.spam_checker_api import RegistrationBehaviour
from synapse.types import RoomAlias
from synapse.util.async_helpers import maybe_awaitable

if TYPE_CHECKING:
    import synapse.events
    import synapse.server

logger = logging.getLogger(__name__)


class SpamChecker:
    def __init__(self, hs: "synapse.server.HomeServer"):
        self.spam_checkers = []  # type: List[Any]
        api = hs.get_module_api()

        for module, config in hs.config.spam_checkers:
            # Older spam checkers don't accept the `api` argument, so we
            # try and detect support.
            spam_args = inspect.getfullargspec(module)
            if "api" in spam_args.args:
                self.spam_checkers.append(module(config=config, api=api))
            else:
                self.spam_checkers.append(module(config=config))

    async def check_event_for_spam(
        self, event: "synapse.events.EventBase"
    ) -> Union[bool, str]:
        """Checks if a given event is considered "spammy" by this server.

        If the server considers an event spammy, then it will be rejected if
        sent by a local user. If it is sent by a user on another server, then
        users receive a blank event.

        Args:
            event: the event to be checked

        Returns:
            True or a string if the event is spammy. If a string is returned it
            will be used as the error message returned to the user.
        """
        for spam_checker in self.spam_checkers:
            if await maybe_awaitable(spam_checker.check_event_for_spam(event)):
                return True

        return False

    async def user_may_invite(
        self, inviter_userid: str, invitee_userid: str, room_id: str
    ) -> bool:
        """Checks if a given user may send an invite

        If this method returns false, the invite will be rejected.

        Args:
            inviter_userid: The user ID of the sender of the invitation
            invitee_userid: The user ID targeted in the invitation
            room_id: The room ID

        Returns:
            True if the user may send an invite, otherwise False
        """
        for spam_checker in self.spam_checkers:
            if (
                await maybe_awaitable(
                    spam_checker.user_may_invite(
                        inviter_userid, invitee_userid, room_id
                    )
                )
                is False
            ):
                return False

        return True

    async def user_may_create_room(self, userid: str) -> bool:
        """Checks if a given user may create a room

        If this method returns false, the creation request will be rejected.

        Args:
            userid: The ID of the user attempting to create a room

        Returns:
            True if the user may create a room, otherwise False
        """
        for spam_checker in self.spam_checkers:
            if (
                await maybe_awaitable(spam_checker.user_may_create_room(userid))
                is False
            ):
                return False

        return True

    async def user_may_create_room_alias(
        self, userid: str, room_alias: RoomAlias
    ) -> bool:
        """Checks if a given user may create a room alias

        If this method returns false, the association request will be rejected.

        Args:
            userid: The ID of the user attempting to create a room alias
            room_alias: The alias to be created

        Returns:
            True if the user may create a room alias, otherwise False
        """
        for spam_checker in self.spam_checkers:
            if (
                await maybe_awaitable(
                    spam_checker.user_may_create_room_alias(userid, room_alias)
                )
                is False
            ):
                return False

        return True

    async def user_may_publish_room(self, userid: str, room_id: str) -> bool:
        """Checks if a given user may publish a room to the directory

        If this method returns false, the publish request will be rejected.

        Args:
            userid: The user ID attempting to publish the room
            room_id: The ID of the room that would be published

        Returns:
            True if the user may publish the room, otherwise False
        """
        for spam_checker in self.spam_checkers:
            if (
                await maybe_awaitable(
                    spam_checker.user_may_publish_room(userid, room_id)
                )
                is False
            ):
                return False

        return True

    async def check_username_for_spam(self, user_profile: Dict[str, str]) -> bool:
        """Checks if a user ID or display name are considered "spammy" by this server.

        If the server considers a username spammy, then it will not be included in
        user directory results.

        Args:
            user_profile: The user information to check, it contains the keys:
                * user_id
                * display_name
                * avatar_url

        Returns:
            True if the user is spammy.
        """
        for spam_checker in self.spam_checkers:
            # For backwards compatibility, only run if the method exists on the
            # spam checker
            checker = getattr(spam_checker, "check_username_for_spam", None)
            if checker:
                # Make a copy of the user profile object to ensure the spam checker
                # cannot modify it.
                if await maybe_awaitable(checker(user_profile.copy())):
                    return True

        return False

    async def check_registration_for_spam(
        self,
        email_threepid: Optional[dict],
        username: Optional[str],
        request_info: Collection[Tuple[str, str]],
        auth_provider_id: Optional[str] = None,
    ) -> RegistrationBehaviour:
        """Checks if we should allow the given registration request.

        Args:
            email_threepid: The email threepid used for registering, if any
            username: The request user name, if any
            request_info: List of tuples of user agent and IP that
                were used during the registration process.
            auth_provider_id: The SSO IdP the user used, e.g "oidc", "saml",
                "cas". If any. Note this does not include users registered
                via a password provider.

        Returns:
            Enum for how the request should be handled
        """

        for spam_checker in self.spam_checkers:
            # For backwards compatibility, only run if the method exists on the
            # spam checker
            checker = getattr(spam_checker, "check_registration_for_spam", None)
            if checker:
                # Provide auth_provider_id if the function supports it
                checker_args = inspect.signature(checker)
                if len(checker_args.parameters) == 4:
                    d = checker(
                        email_threepid,
                        username,
                        request_info,
                        auth_provider_id,
                    )
                elif len(checker_args.parameters) == 3:
                    d = checker(email_threepid, username, request_info)
                else:
                    logger.error(
                        "Invalid signature for %s.check_registration_for_spam. Denying registration",
                        spam_checker.__module__,
                    )
                    return RegistrationBehaviour.DENY

                behaviour = await maybe_awaitable(d)
                assert isinstance(behaviour, RegistrationBehaviour)
                if behaviour != RegistrationBehaviour.ALLOW:
                    return behaviour

        return RegistrationBehaviour.ALLOW

    async def check_media_file_for_spam(
        self, file_wrapper: ReadableFileWrapper, file_info: FileInfo
    ) -> bool:
        """Checks if a piece of newly uploaded media should be blocked.

        This will be called for local uploads, downloads of remote media, each
        thumbnail generated for those, and web pages/images used for URL
        previews.

        Note that care should be taken to not do blocking IO operations in the
        main thread. For example, to get the contents of a file a module
        should do::

            async def check_media_file_for_spam(
                self, file: ReadableFileWrapper, file_info: FileInfo
            ) -> bool:
                buffer = BytesIO()
                await file.write_chunks_to(buffer.write)

                if buffer.getvalue() == b"Hello World":
                    return True

                return False


        Args:
            file: An object that allows reading the contents of the media.
            file_info: Metadata about the file.

        Returns:
            True if the media should be blocked or False if it should be
            allowed.
        """

        for spam_checker in self.spam_checkers:
            # For backwards compatibility, only run if the method exists on the
            # spam checker
            checker = getattr(spam_checker, "check_media_file_for_spam", None)
            if checker:
                spam = await maybe_awaitable(checker(file_wrapper, file_info))
                if spam:
                    return True

        return False
