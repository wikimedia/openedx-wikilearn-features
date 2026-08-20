"""
Client to handle WikiMetaClient requests.
"""
import asyncio
import json
import logging
import urllib.parse

import aiohttp
from django.conf import settings
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers

logger = logging.getLogger(__name__)


class WikiMetaClient(object):
    """
    Client for Meta API requests.
    """
    # mclimit above 500 is rejected with a warning and silently clamped by Meta.
    _API_MESSAGE_COLLECTION_LIMIT = 500
    # A failed request is retried this many times in total, with a growing pause in between,
    # but only when the failure looks transient i.e a transport error or a throttling response.
    _API_MAX_ATTEMPTS = 3
    _API_RETRY_BACKOFF_IN_SECONDS = 5
    _RETRYABLE_ERROR_CODES = ('ratelimited', 'maxlag', 'readonly', 'internal_api_error_DBQueryError')

    def __init__(self):
        """
        Constructs a new instance of the Wiki Meta client.
        """
        self._BASE_URL = configuration_helpers.get_value(
                'WIKI_META_BASE_URL', settings.WIKI_META_BASE_URL)
        self._BASE_API_URL = configuration_helpers.get_value(
                'WIKI_META_BASE_API_URL', settings.WIKI_META_BASE_API_URL)
        self._CONTENT_MODEL = configuration_helpers.get_value(
                'WIKI_META_CONTENT_MODEL', settings.WIKI_META_CONTENT_MODEL)
        self._MCGROUP_PREFIX = configuration_helpers.get_value(
                'WIKI_META_MCGROUP_PREFIX', settings.WIKI_META_MCGROUP_PREFIX)
        self._COURSE_PREFIX = configuration_helpers.get_value(
                'WIKI_META_COURSE_PREFIX', settings.WIKI_META_COURSE_PREFIX)
        self._API_REQUEST_DELAY = configuration_helpers.get_value(
                'WIKI_META_API_REQUEST_DELAY_IN_SECONDS', settings.WIKI_META_API_REQUEST_DELAY_IN_SECONDS)
        self._API_GET_REQUEST_SYNC_LIMIT = configuration_helpers.get_value(
                'WIKI_META_API_GET_REQUEST_SYNC_LIMIT', settings.WIKI_META_API_GET_REQUEST_SYNC_LIMIT)
        
        if not self._COURSE_PREFIX:
            self._COURSE_PREFIX = ''
        
        if not self._BASE_URL or not self._BASE_API_URL or not self._CONTENT_MODEL or not self._MCGROUP_PREFIX:
            raise Exception("META CLIENT ERROR - Missing WIKI Meta Configurations.")

        self._API_USERNAME = configuration_helpers.get_value(
                'WIKI_META_API_USERNAME', settings.WIKI_META_API_USERNAME)
        self._API_PASSWORD = configuration_helpers.get_value(
                'WIKI_META_API_PASSWORD', settings.WIKI_META_API_PASSWORD)

        if not self._API_USERNAME or not self._API_PASSWORD:
            raise Exception("META CLIENT ERROR - Missing WIKI Meta API Credentials.")

        self._BASE_API_END_POINT = configuration_helpers.get_value(
                'WIKI_META_BASE_API_END_POINT', self._BASE_API_URL)
        self._BASE_REDIRECT_URL = configuration_helpers.get_value(
                'WIKI_META_BASE_REDIRECT_URL', self._BASE_URL)

        logger.debug(
            "Created meta client with base_url: %s, api_url: %s, redirect_url: %s.",
            self._BASE_URL, self._BASE_API_END_POINT, self._BASE_REDIRECT_URL,
        )

    @property
    def wikimedia_user_agent(self):
        client = getattr(settings, "PLATFORM_NAME", "wikilearn")
        site = getattr(settings, "LMS_ROOT_URL", "https://learn.wiki/")
        contact_mail = getattr(settings, "CONTACT_EMAIL", "comdevteam@wikimedia.org")
        return f'{client}/0.13 ({site}; {contact_mail})'

    def get_page_redirect_url_for_title(self, title):
        """
        Returns page redirect url for given title.
        On meta server send_call create pages with all course block data items i.e display_name and content. For created pages
        Meta server creates message groups of translations.
        Note: Successfull creation of pages do not imply successful creation of message groups.
        """
        if title:
            return "{}/{}".format(self._BASE_REDIRECT_URL, title)

    @staticmethod
    def normalize_language_code(language_code):
        """
        This is because meta api expects hyphen instead of underscore.
        """
        return language_code.replace('_', '-').lower()

    def get_expected_message_group_redirect_url(self, source_page_title, target_language):
        """
        Returns expected redirect url of meta server from where user can translate content.
        Term "expected" is used as we are not sure if message groups for translation have been created or not.
        """
        url = "{}/Special:Translate?group={}-{}&language={}".format(
            self._BASE_REDIRECT_URL, self._MCGROUP_PREFIX, urllib.parse.quote(source_page_title), WikiMetaClient.normalize_language_code(target_language)
        )
        return url

    def _seprate_course_prefix_from_string(self, value):
        """
        Seprate course prifex from the string if exists
        Arguments:
            value: (str) [CoursePrefix]Course-v1:edX+fresh1+fresh1/en/block-v1:edX+fresh1+fresh1+type@problem+block@9eefa6c9923346b1b746988401c638ad/display_name
        Returns:
            (str) [CoursePrefix]
            (str) Course-v1:edX+fresh1+fresh1/en/block-v1:edX+fresh1+fresh1+type@problem+block@9eefa6c9923346b1b746988401c638ad/display_name
        """
        if self._COURSE_PREFIX:
            if value.startswith(self._COURSE_PREFIX):
                return self._COURSE_PREFIX, value[len(self._COURSE_PREFIX):]
            elif value.startswith(self._COURSE_PREFIX.replace('_', ' ')):
                return self._COURSE_PREFIX.replace('_', ' '), value[len(self._COURSE_PREFIX):]
        return "", value
    
    def _process_fetched_response_data_list_to_dict(self, response_data):
        """
        Converts response message collections list to dictionary so that later on traversing will be easy.

        Sample response data:
        [
            {
                "key": "[CoursePrefix]Course-v1:edX+fresh1+fresh1/en/block-v1:edX+fresh1+fresh1+type@problem+block@9eefa6c9923346b1b746988401c638ad/display_name",
                "translation": "चेक बॉक्",
                "properties": {
                    "status": "translated",
                    "last-translator-text": "wikimeta-translator-username",
                    "last-translator-id": "wikimeta-translator-userid",
                },
                "title": "Translations:[CoursePrefix]Course-v1:edX+fresh1+fresh1/en/block-v1:edX+fresh1+fresh1+type@problem+block@9eefa6c9923346b1b746988401c638ad/display_name/hi",
                "targetLanguage": "hi",
                "primaryGroup": "messagebundle-[CoursePrefix]Course-v1:edX+fresh1+fresh1/en/block-v1:edX+fresh1+fresh1+type@problem+block@9eefa6c9923346b1b746988401c638ad",
            }
            ...
        ]

        Returns converted dict:
        {
            "display_name": {
                "key": "Course-v1:edX+fresh1+fresh1/en/block-v1:edX+fresh1+fresh1+type@problem+block@9eefa6c9923346b1b746988401c638ad/display_name",
                "translation": "चेक बॉक्",
                "properties": {
                    "status": "translated",
                    "last-translator-text": "wikimeta-translator-username",
                    "last-translator-id": "wikimeta-translator-userid",
                },
                "title": "Translations:[CoursePrefix]Course-v1:edX+fresh1+fresh1/en/block-v1:edX+fresh1+fresh1+type@problem+block@9eefa6c9923346b1b746988401c638ad/display_name/hi",
                "targetLanguage": "hi",
                "primaryGroup": "messagebundle-[CoursePrefix]Course-v1:edX+fresh1+fresh1/en/block-v1:edX+fresh1+fresh1+type@problem+block@9eefa6c9923346b1b746988401c638ad",
            }
        }
        """
        response_dict = {}
        for response_translation_obj in response_data:
            key = response_translation_obj.get("key", None)
            if key:
                _, response_translation_obj['key'] = self._seprate_course_prefix_from_string(key)
                try:
                    block_key = response_translation_obj.get('key').split("/")[3]
                except IndexError:
                    logger.error("Unable to read a data type out of Meta response key: %s.", key)
                    continue
                response_dict.update({block_key: response_translation_obj})
        return response_dict


    @staticmethod
    def _request_summary(request_params, request_data):
        """
        Returns a short identifier of a request for log lines, so that a failure can be traced back
        to a message group without dumping the whole request. Page text and credentials are left out.
        """
        source = request_params or request_data or {}
        summary = {key: source.get(key) for key in ('action', 'mcgroup', 'mclanguage', 'title') if source.get(key)}
        return json.dumps(summary, ensure_ascii=False)

    async def parse_response(self, request_params, request_data, response):
        """
        Parses and return the response.
        """
        summary = self._request_summary(request_params, request_data)
        try:
            data = await response.json()
        except (aiohttp.ContentTypeError, ValueError, aiohttp.ClientError) as e:
            logger.error(
                "Meta API response could not be decoded for request %s, status %s: %s: %s.",
                summary, response.status, type(e).__name__, e,
            )
            logger.debug("Meta API response content: %s", await response.text())
            return False, None

        if data is not None and response.status in [200, 201]:
            error = data.get('error') or {}
            if error:
                logger.error(
                    "Meta API returned error '%s' for request %s: %s",
                    error.get('code'), summary, error.get('info'),
                )
                return False, data

            if data.get('warnings'):
                logger.warning(
                    "Meta API returned warnings for request %s: %s",
                    summary, json.dumps(data.get('warnings'), ensure_ascii=False),
                )

            logger.debug("Meta API success response for request %s: %s", summary, json.dumps(data))
            return True, data

        logger.error(
            "Meta API returned status %s for request %s: %s",
            response.status, summary, json.dumps(data, ensure_ascii=False)[:500],
        )
        return False, data


    async def handle_request(self, request_call, params=None, data=None):
        """
        Handles all Meta API calls.

        A transport level failure is reported the same way as a rejected response, so that a single
        broken request cannot abort a whole sync run through asyncio.gather.
        """
        headers = {'User-Agent': self.wikimedia_user_agent}
        summary = self._request_summary(params, data)
        logger.debug("Sending Meta request %s with headers: %s.", summary, headers)
        try:
            response = await request_call(url=self._BASE_API_END_POINT, params=params, data=data, headers=headers)
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            logger.error(
                "Meta API request %s failed to complete: %s: %s.", summary, type(error).__name__, error
            )
            return False, None

        return await self.parse_response(params, data, response)

    def _is_retryable(self, response_data):
        """
        Returns True if a failed response looks transient and is worth retrying.
        """
        if response_data is None:
            # Transport error, or a body we could not decode.
            return True
        return (response_data.get('error') or {}).get('code') in self._RETRYABLE_ERROR_CODES


    async def fetch_login_token(self, session):
        logger.debug("Initiate Meta login token request.")
        params = {
            "action": "query",
            "meta": "tokens",
            "type": "login",
            "format": "json",
            "formatversion": 2
        }
        success, response_data = await self.handle_request(session.get, params=params, data=None)
        if success:
            token = response_data.get('query', {}).get('tokens', {}).get('logintoken', {})
            logger.debug("Login token has been fetched.")
            return token


    async def login_request(self, session):
        token  = await self.fetch_login_token(session)
        if not token:
            raise Exception("Meta Client Error: Unable to get Login Token from Meta.")

        logger.debug("Initiate Meta login request with generated login-token.")
        post_data = {
           "action": "login",
           "lgname": self._API_USERNAME,
           "lgpassword": self._API_PASSWORD,
           "lgtoken": token,
           "format": "json",
           "formatversion": 2
        }

        success, data = await self.handle_request(session.post, params=None, data=post_data)
        if success and data.get('login', {}).get('result', '') == 'Success':
            logger.info("Login request is successfull")
        else:
            raise Exception(f"Meta Client Error: Failed login request with the following response: {data}")


    async def fetch_csrf_token(self, session):
        logger.debug("Initiate Meta CSRF token request.")
        params = {
            "action": "query",
            "meta": "tokens",
            "format": "json",
            "formatversion": 2
        }
        success, response_data = await self.handle_request(session.get, params=params, data=None)
        if success:
            csrf_token = response_data.get('query', {}).get('tokens', {}).get('csrftoken', {})
            logger.debug("CSRF token has been fetched.")
            return csrf_token


    async def create_update_message_group(self, title, text, session, csrf_token, summary="update_content"):
        data = {
            "action": "edit",
            "format": "json",
            "title": '{}{}'.format(self._COURSE_PREFIX, title),
            "text": json.dumps(text),
            "summary": summary,
            "contentmodel": self._CONTENT_MODEL,
            "token": csrf_token,
            "bot": 1,
        }

        success, response_data = await self.handle_request(session.post, params=None, data=data)
        if success:
            response_edit_dict = response_data.get("edit", {})
            
            # removes course prefix form response title and add title_prefix to the response
            title = response_edit_dict.get('title')
            response_edit_dict['title_prefix'], response_edit_dict['title'] = self._seprate_course_prefix_from_string(title)
            logger.info("Message group has been updated for component: %s and pageid: %s .",
                        response_edit_dict.get('title'),
                        response_edit_dict.get('pageid')
            )
            return response_edit_dict


    async def sync_translations(self, mcgroup, mclanguage, session):
        """
        Fetches the translations of a message group in one language.

        Always returns a dict. On failure the 'failed' flag is set instead of returning None, so that
        callers can tell a group with no translations apart from a group we never managed to read.
        """
        updated_mcgroup = (self._COURSE_PREFIX + mcgroup).replace("_", " ")
        updated_mcgroup = updated_mcgroup[0].upper() + updated_mcgroup[1:]
        params = {
            "action": "query",
            "format": "json",
            "list": "messagecollection",
            "utf8": 1,
            "formatversion": 2,
            "mcgroup": "{}-{}".format(self._MCGROUP_PREFIX, updated_mcgroup),
            "mclanguage": mclanguage,
            "mcprop": "translation|properties",
            "mclimit": self._API_MESSAGE_COLLECTION_LIMIT
        }

        # mcgroup is in this format: source_course_id/source_lang_code/source_block_key
        result = {
            'response_source_block': mcgroup.split("/")[2],
            'mclanguage': mclanguage,
            'response_data': {},
            'failed': True,
        }

        for attempt in range(1, self._API_MAX_ATTEMPTS + 1):
            success, response_data = await self.handle_request(session.get, params=params, data=None)
            if success:
                break

            if attempt == self._API_MAX_ATTEMPTS or not self._is_retryable(response_data):
                logger.error(
                    "Giving up on message group %s in language %s after %d attempt(s).",
                    updated_mcgroup, mclanguage, attempt,
                )
                return result

            delay = self._API_RETRY_BACKOFF_IN_SECONDS * attempt
            logger.warning(
                "Retrying message group %s in language %s in %ss, attempt %d of %d.",
                updated_mcgroup, mclanguage, delay, attempt + 1, self._API_MAX_ATTEMPTS,
            )
            await asyncio.sleep(delay)

        translation_state = response_data.get('query', {}).get('metadata', {}).get('state', "")
        logger.debug("Translation state %s for %s in %s.", translation_state, mcgroup, mclanguage)

        result['response_data'] = self._process_fetched_response_data_list_to_dict(
            response_data.get('query', {}).get('messagecollection', [])
        )
        result['failed'] = False
        return result
