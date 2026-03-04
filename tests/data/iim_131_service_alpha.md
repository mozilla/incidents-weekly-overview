***Instruction:***

1. *Replace (delete and clear format) instructions that are in \<brackets\> with text for your section (and don’t forget to delete instructions like this). Please also set sharing/permissions on the doc to (at least) Commentable or Editable by all Mozillians (unless you feel this is a security or otherwise sensitive incident which requires protection). Please be sure your doc is editable by [Cassandra](mailto:cassandra@example.com), [William](mailto:william@example.com), [Paul](mailto:paul@example.com), and [Hamid](mailto:hamid@example.com).*  
2. *Within 48hrs of your incident being mitigated (i.e. you’ve stopped your live incident call and are working on any follow-up issue during business hours), your doc should be readied. After that, and/or when you feel it’s ready, ping [Cassandra](mailto:cassandra@example.com), [William](mailto:william@example.com), and [Hamid](mailto:hamid@example.com). They’ll do active reviews/comments in the subsequent days. [See the documentation on incident reports](https://example.com/wiki/x/CIC3c).*  
3. *Within one week of \#2, comments should be resolved and your doc should be in a readied state for incident review. Please note that the owner of the service is responsible for having their doc ready and for presenting during monthly incident reviews (even if you got help from Cloud Engineering \[formerly SRE\] during your incident for your service). [See the incident report completion checklist](https://example.com/wiki/spaces/MIR/pages/1934656300/Incident+report+completion+checklist).*

# Incident: Service Alpha in a degraded state

*\<Please ensure incident titles are updated to be specific and clear ahead of postmortem reviews.*  
[*See the documentation.*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)  
*/\>*

All times are written in UTC. Use 24-hour clock and "YYYY-MM-DD hh:mm" formatting. Use Google Doc chips for people, but not for dates. [See the documentation](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports).

| Incident Severity | *Consider the business impact as you set this Severity. Refer to [this guide](https://example.com/wiki/spaces/MIR/pages/20512894/Incident+Severity+Levels). If the priority of your incident changes during its lifecycle, please capture this in the Timeline section and one of the written sections. Include rationale for why you assigned this severity level.* S2 \- High Rationale: This was not immediately affecting the production environment, but if not mitigated it would eventually cause end users to see no content.  |
| :---- | :---- |
| **Incident Title** | Service Alpha in a degraded state |
| **Jira Ticket/Bug Number** | [IIM-131](https://example.com/browse/IIM-131) |
| **Time of first Impact** | *This is the time the impact first started.* 2026-02-21 08:57 |
| **Time Detected** | *Our automation detected a deviation from normal service health.* 2026-02-21 23:44 |
| **Time Alerted** | *PagerDuty sent its first alert/page.* 2026-02-22 00:14 |
| **Time Acknowledged** | *The first page was ACK'd, or in some other way a responding engineer acknowledged the incident.* 2026-02-22 00:15 |
| **Time Responded/Engaged** | *First moment the problem was being engaged (i.e. reading errors, graphs, etc to begin understanding what was wrong / why the alert even triggered)* 2026-02-22 00:24 |
| **Time Mitigated (Repaired)** | *Service was restored to normal from our users perspective, even if it meant we still had to do continued work behind the scenes to be done with the risk of further service degradation.* 2026-02-22 01:32 |
| **Time Resolved** | *Mitigated\!=Resolved. The service was healthy enough to operate such that we could continue further work on it during business hours (i.e. we were done with the urgent need to be on call or do work which could extend into outside business hours, in order to keep the service up).* 2026-02-22 02:07 |
| **Issue detected via** | **Manual/Human** |
| **Video Call Link** |  |
| **Slack Channel** | [\#incident-service-alpha-2026-02-21](https://example.com/archives/C0AH7DWAEMN) |
| **Current Status** | **Mitigated** |

## Who’s on point

*\<At minimum we should have the top 3 roles for any incident (Incident Commander, Comms, Engineers). Add more where needed (this saves time, biasing for speed of execution, rather than having people delete rows). After the incident is done, please move this section to the bottom of the document.*  
[*See the documentation*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)*.*  
*/\>*

| Role | Name (slack handle) | Notes / supporting docs |
| :---- | :---- | :---- |
| **Incident Commander[^1]** | [Steven](mailto:steven@example.com) |  |
| **Communications** | \<enter names here using @- tagging\> | *Which one person is communicating inside Mozilla (to all)? Which one person is communicating with the public? Which one person is communicating with any other stakeholders not listed above (external partners, press, Mozilla execs, etc)?* |
| **Engineer(s)** | [Steven](mailto:steven@example.com) [Jason](mailto:jason@example.com) [Brandon](mailto:brandon@example.com) [Nan](mailto:nan@example.com) [Rolf](mailto:rolf@example.com) | *Put a parenthesis next to each person’s name who is working on this incident (during the incident, to resolve it), to help us identify any extra info about them that is pertinent to the problem (or, don’t leave a parentheses and just write names).* Examples: @nameA (primary on-call) @nameB (secondary on-call) @nameC (\<service-name\> engineer) @nameD (Browser Incident Engineering Lead)  |
| Other (Common Browser Incident Roles, remove if not needed) |  |  |
| Support |  |  |
| QA |  |  |
| Release Manager |  |  |
| Release Engineer |  |  |
| Metrics/Data |  |  |

## Timeline

*\<Note: if you change the severity of your incident, please capture that here and somewhere in one of the written sections. After the incident is done, please move this section to the bottom of the document. This document is not ready for review until this section is moved.*  
[*See the documentation.*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)  
*/\>*

| YYYY-MM-DD hh:mm | Person(s) | Note/comment/action |
| :---- | :---- | :---- |
| 2026-02-21 20:48 |  | Thing API avg memory is 99% across 4 tasks |
| 2026-02-21 20:57 |  | Thing API traffic from Service Alpha goes up 6x |
| 2026-02-21 23:44 | [Rolf](mailto:rolf@example.com) | Rolf adds a message to the \#incidents channel that the Thing API is down and its affecting Service Alpha/New Tab |
| 2026-02-22 00:01 | [Chris](mailto:chris@example.com) | Chris paged cloudengineeringescalations |
| 2026-02-22 00:22 | [Paul](mailto:paul@example.com) | Incident officially declared |
| 2026-02-22 01:28 | [Steven](mailto:steven@example.com) | Scaled Thing API to 10 tasks, suspended all scaling actions |
| 2026-02-22 01:30 |  | Thing API traffic is back to normal |
| 2026-02-22 02:05 | [Jason](mailto:jason@example.com) | Restarted Service Alpha pods |
| 2026-02-22 02:09 | [Jason](mailto:jason@example.com)[Nan](mailto:nan@example.com) | Incident declared mitigated |
| 2026-02-24 18:12 | [Jonathan](mailto:jonathan@example.com) | Resolves Thing API Sentry memory leak [\#368](https://example.com/ContentService/content-monorepo/pull/368) |
| 2026-02-24 21:54 | [Matt](mailto:matt@example.com) | Resolves Service Alpha negative caching issue [\#1284](https://example.com/mozilla-services/service-alpha-py/pull/1284) |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |

# Impact

*\<What is the impact of this incident? It’s ok to use “current tense” during the incident, and past-tense once you switch to writing the postmortem. For the postmortem, the opening statement of this section should be something like “on \<date\> from \<time1\> to \<time2\>, \<description of impact that was happening, and who was impacted\>.” Some things to consider covering:*

* *Are end-users not able to do something (e.g. 90% of Browser users were unable to login to their Mozilla accounts)?*  
* *Are Mozilla engineers blocked from something (e.g. On \<date\> from \<time1\> to \<time2\> 100% of Mozilla engineers could not ship code to production. Though production was working ok, if one issue had arisen which needed a fast change we would have been unable to ship it)?*  
* *Are there risks of this getting worse, if so what things would contribute to that risk (e.g. time)?*

[*See the documentation*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)*.*  
*/\>*  
On Feb 21st, Service Alpha failed to respond to requests for Things for 4.5 hours. There was no user impact, because Browser continued to display New Tab recommendations from cache, and thanks to the response by Jason and Nan. Stories on New Tab were stale during this period, but there was no noticeable drop in engagement from a baseline.

IMAGE HERE

# Description of the issue

*\<A summary of the events that happened from the first moment of impact (even if we hadn’t detected the issue by then), what happened as we Detected (i.e. our alerts told us or a user told us), Acknowledged (e.g. we ACK’d the page, even if we didn’t start to work no it), Responded/Engaged (i.e. we started working on it), Mitigated (we stopped the impact from being material, even if temporarily), Resolved (we ensured the impact will not return for a substantial amount of time, even with a temporary fix in place, until we take on longer term postmortem action items.)*  
[*See the documentation.*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)  
*\>*  
On Jan 27, Sentry packages [were updated in content-monorepo](https://example.com/ContentService/content-monorepo/commit/27e3b80e935ec07f658faad21c080276ee6f67b9), which includes the Thing API. This started a slow memory leak that went unnoticed. It led to all four tasks running out of memory every 3 days.

On 2026-02-21 between 08:48 \- 08:55, the Thing API tasks again ran out of memory. Unlike before, this corresponded with a sudden spike in traffic from Service Alpha. A lack of negative caching in Service Alpha caused this amplification: when a cache refresh failed, the cache entry's expiration was not extended, so the next request after each failed retry cycle immediately triggered another cycle instead of waiting for the next TTL window (\~60s). With 268 Service Alpha pods each independently retrying, this created a sustained retry storm that overwhelmed the already-struggling Thing API.

I think it’s partly a coincidence that this issue did not manifest the first six times that the Thing API reached near 99% memory usage since the Sentry update on 01/27, possibly because at least one task was still able to respond while the others were crashing.

IMAGE HERE

IMAGE HERE

IMAGE HERE

# Contributing Factors

*\<Why did this issue happen? Not just at a surface level, but be sure to probe into the causes for anything which happened that wasn’t ideal. The goal is to find the multiple, possibly related (but possibly not related), contributing factors, the confluence of which culminated into this incident. For example instead of traditional “5 why’s” think about “multiple trees of why’s” \- avoid the temptation/pitfall of looking for “just one root cause.”. As you dive into each “five why,” don’t stop at identifying something that “just broke,” follow it to the depth that gives you potential actions we can take to avoid that situation in the future.*  
[*See the documentation.*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)  
*/\>*   
In 2025 H1, the Home & New Tab backend team performed weekly operational reviews with monthly service retrospectives, however this process was abandoned due to high workload, partially from the ContentService shut-down. This process would have caught the memory leak earlier.

# Postmortem Action Items

*\<What are we going to do to prevent recurrence of this issue in our domain, prevent potentially similar issues this incident+postmortem has made us realize are risks, and/or help others in Mozilla prevent these types of issues; this should include tangible actions resulting from things like “lessons learned”; this should include links to jira tickets which are filed for every postmortem action item. **This section is not complete (thus the postmortem is not ‘done’) until jira tickets have been created with ETAs (tentative dates are ok), linked to the ticket for this incident, and listed in the table below.***  
[*See the documentation.*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)  
*/\>*

| Jira Ticket \+ Status | Ticket Title / Context / Summary / Reason |
| :---- | :---- |
| \[[JIRA-123](https://example.com/browse/)\] Status: Done | *\<Ticket Title\> \<Context / Summary / Reason. Provide some context and/or info around this action item\>* |
|  |  |
|  |  |

# \[optional\] Postmortem discussion notes

*\<Anything we want to capture as notes during postmortem discussion. This could be a place to capture notes (who said/shared what, etc). However this is not a place where any form of follow-up or action items go. Instead, those should go into the Postmortem Action Items section. Notice this postmortem doc doesn’t have a “lessons learned” section (or other similar ones), that too goes into Postmortem Action items (if it’s not worth taking specific steps to improve, then it arguably wasn’t a “lesson learned”). The best version of this section is when it is left blank because all the postmortem discussion focused on ensuring the previous sections were correct, and resulted in Postmortem Action Items which helped prevent recurrence of this issue and ones like it across as much of the company as possible.\>*

[PagerDuty services](https://example.com/service-directory) look to be configured for CorpusAPI, including a CloudWatch integration on the [production service](https://example.com/service-directory/PBM69SO/activity); however, the production PagerDuty service did not trigger during the incident.

# \[optional\] Appendix:

*\<Any additional information that may be of use. For example:*

* *Architecture about your service, to help provide context for the reader*  
* *Captured output*  
* *sampled error*  
* *etc.*

*/\>*  


[^1]:  **Incident Commanders** lead and manage the response to an incident. **Incident Managers** oversee broader incident management processes focusing on strategic planning and resource allocation. See expanded definition [here](https://example.com/wiki/spaces/MIR/pages/20512894/Incident+Severity+Levels).