***Instruction:***

1. *Replace (delete and clear format) instructions that are in \<brackets\> with text for your section (and don’t forget to delete instructions like this). Please also set sharing/permissions on the doc to (at least) Commentable or Editable by all Mozillians (unless you feel this is a security or otherwise sensitive incident which requires protection). Please be sure your doc is editable by [Cassandra](mailto:cassandra@example.com), [William](mailto:william@example.com), [Paul](mailto:paul@example.com), and [Hamid](mailto:hamid@example.com).*  
2. *Within 48hrs of your incident being mitigated (i.e. you’ve stopped your live incident call and are working on any follow-up issue during business hours), your doc should be readied. After that, and/or when you feel it’s ready, ping [Cassandra](mailto:cassandra@example.com), [William](mailto:william@example.com), and [Hamid](mailto:hamid@example.com). They’ll do active reviews/comments in the subsequent days. [See the documentation on incident reports](https://example.com/wiki/x/CIC3c).*  
3. *Within one week of \#2, comments should be resolved and your doc should be in a readied state for incident review. Please note that the owner of the service is responsible for having their doc ready and for presenting during monthly incident reviews (even if you got help from Cloud Engineering \[formerly SRE\] during your incident for your service). [See the incident report completion checklist](https://example.com/wiki/spaces/MIR/pages/1934656300/Incident+report+completion+checklist).*

# Incident: 2024-02-24: BravoService swamped by external notifications

*\<Please ensure incident titles are updated to be specific and clear ahead of postmortem reviews.*  
[*See the documentation.*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)  
*/\>*

All times are written in UTC. Use 24-hour clock and "YYYY-MM-DD hh:mm" formatting. Use Google Doc chips for people, but not for dates. [See the documentation](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports).

| Incident Severity | *Consider the business impact as you set this Severity. Refer to [this guide](https://example.com/wiki/spaces/MIR/pages/20512894/Incident+Severity+Levels). If the priority of your incident changes during its lifecycle, please capture this in the Timeline section and one of the written sections. Include rationale for why you assigned this severity level.* S3 \- Medium Rationale: Some notifications are succeeding, but due to volume, autoendpoint is struggling to handle the load and some nodes bail on startup. Affected users will not see any active indication of an issue – they will not receive a notification (and therefore, they don’t know that there’s a notification they should be receiving). Because this affects a subset of Firefox users, and including a subset of those that are Bravo users, this is medium severity. |
| :---- | :---- |
| **Incident Title** | BravoService swamped by external notifications |
| **Jira Ticket/Bug Number** | [IIM-133](https://example.com/browse/IIM-133)  |
| **Time of first Impact** | *This is the time the impact first started.* 2026-02-24 13:10 |
| **Time Detected** | *Our automation detected a deviation from normal service health.* 2026-02-24 13:10  |
| **Time Alerted** | *PagerDuty sent its first alert/page (second time is the Bravo alert — this was the only PD alert received)* 2026-02-24 13:10    || 2026-02-24 13:37 |
| **Time Acknowledged** | *The first page was ACK'd, or in some other way a responding engineer acknowledged the incident.* 2026-02-24 14:24  || 2026-02-24 13:38 |
| **Time Responded/Engaged** | *First moment the problem was being engaged (i.e. reading errors, graphs, etc to begin understanding what was wrong / why the alert even triggered)* 2026-02-24 16:15  || 2026-02-24 13:50 |
| **Time Mitigated (Repaired)** | *Service was restored to normal from our users perspective, even if it meant we still had to do continued work behind the scenes to be done with the risk of further service degradation.* 2026-02-24 18:43 |
| **Time Resolved** | *Mitigated\!=Resolved. The service was healthy enough to operate such that we could continue further work on it during business hours (i.e. we were done with the urgent need to be on call or do work which could extend into outside business hours, in order to keep the service up).* 2026-02-24 18:43 |
| **Issue detected via** | **Automated Alert** |
| **Video Call Link** |  |
| **Slack Channel** | \#push |
| **Current Status** | **Mitigated** |

## Who’s on point

*\<At minimum we should have the top 3 roles for any incident (Incident Commander, Comms, Engineers). Add more where needed (this saves time, biasing for speed of execution, rather than having people delete rows). After the incident is done, please move this section to the bottom of the document.*  
[*See the documentation*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)*.*  
*/\>*

| Role | Name (slack handle) | Notes / supporting docs |
| :---- | :---- | :---- |
| **Incident Commander[^1]** | [Anna](mailto:anna@example.com) |  |
| **Communications** |  [Anna](mailto:anna@example.com) | *Which one person is communicating inside Mozilla (to all)? Which one person is communicating with the public? No way to know who is subscribed to push notifications Which one person is communicating with any other stakeholders not listed above  Internal teams who rely on Push (Bravo) have been notified.*   |
| **Engineer(s)** | [JR](mailto:jr@example.com) | *Put a parenthesis next to each person’s name who is working on this incident (during the incident, to resolve it), to help us identify any extra info about them that is pertinent to the problem (or, don’t leave a parentheses and just write names).* Examples: @nameA (primary on-call) @nameB (secondary on-call) @nameC (\<service-name\> engineer) @nameD (Firefox Incident Engineering Lead)  |
| Other (Common Firefox Incident Roles, remove if not needed) |  |  |
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
| 2026-02-24 13:10 UTC | Yardstick Alert | First alert appears on BravoService dashboard for Push send failures for Bravo. [Link](https://example.com/d/do4mmwcVz/bravoservice-gcp): |
| 2026-02-24 13:38 UTC | Yardstick Alert | First alert appears on Bravo Dashboards for spike in 504 errors. [Link](https://example.com/d/feht7f4wub5s0e/overall-infrastructure-health) .  Continues to alert.  |
| 2026-02-24 14:06 UTC | [Reino](mailto:reino@example.com) | Notes he is seeing some [big spikes in 504s](https://example.com/d/eeg8urqqeydq8f/subscription-platform) for auth-server on a private team channel. |
| 2026-02-24 14:24 UTC | [Barry](mailto:barry@example.com) | Barry pings the \#push channel to let the team know about the issue |
| 2026-02-24 15:50 UTC | [JR](mailto:jr@example.com) | Acknowledged the ping in the \#push channel and started investigating |
| 2026-02-24 16:06 UTC | [Wil](mailto:wil@example.com) | Notes the firewall is also seeing 504s and the response time for all of them is \~10s indicating connections are timing out. |
| 2026-02-24 16:07 UTC | [JR](mailto:jr@example.com) | JR updates the team via thread: Looking at the graphs, it appears that we have a flood of inbound notifications. (Increased CPU and memory on the autoendpoint nodes) Somewhat disturbingly, the failures are "unknown" meaning that the UA has no idea why the message failed, possibly due to the service worker crashing.) |
| 2026-02-24 16:18  UTC | [JR](mailto:jr@example.com) | Identifies a bunch of degraded endpoints due to OOM. |
| 2026-02-24 16:23  UTC | [David](mailto:david@example.com) | Informs the team that we should start an incident and identifies the incident manager. |
| 2026-02-24 16:45 UTC | [JR](mailto:jr@example.com) | JR Merges a patch to increase autoendpoint memory to address degraded nodes: [https://example.com/mozilla/webservices-infra/pull/9754](https://example.com/mozilla/webservices-infra/pull/9754)   |
| 2026-02-24 16:52  UTC | [David](mailto:david@example.com) | Reports the incident in the \#incidents slack channel  |
| 2026-02-24 18:34 UTC  | [Dan](mailto:dan@example.com) | Did some analysis of traffic on /account/devices/notify endpoint and saw a large amount of traffic coming from a relatively small number of IPs. New rate limiting rules are being applied with this [PR](https://example.com/mozilla/webservices-infra/pull/9664). The big query that shows bucked IPs per time window is [here](https://example.com/bigquery). Note, that traffic had subsided before these changes were applied, see graph [here](https://example.com/d/J81nRFfWz/auth-server). To see queries and raw data, see this: [https://example.com/spreadsheets/d/sheetid/edit](https://example.com/spreadsheets/d/sheetid/edit)  |
| 2026-02-2418:43 UTC | [JR](mailto:jr@example.com) | Traffic appears to be back to normal with nominal load for most things. There is still high memory usage for Bravoendpoint, but that's a known issue. |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |
|  |  |  |

# Impact

Seeing degraded performance of the Bravoendpoint nodes during a large incoming wave of subscription updates. The logs are indicating that the Bravoendpoint nodes are failing due to OOM issues. This outage is causing a lower number of messages to be processed with automatic node starts failing.

This incident is ongoing and subject to investigation.

# Description of the issue

Bravoendpoint is returning a large number of 500 class errors. This appears to be due to a very high number of incoming subscriptions to Autoendoint which was causing autoendpoint to OOM. Concerningly, this same OOM error was happening with new nodes that were being brought online which was causing nodes to fail to start. 

[Doubling the amount of memory](https://example.com/mozilla/webservices-infra/pull/9754) for autoendpoint resolved the node start problem (but doesn't answer why the nodes are running out of memory to begin with)  

# Contributing Factors

The previous deployment for BravoService was [Thu Jan 22 2026 08:45:27 GMT-0800](https://example.com/applications/argocd-webservices/bravoservice-prod-us-west1-autoendpoint). 

It is very difficult to determine a lot of detailed information about BravoService because much of it requires high cardinality (e.g. UAIDs and Channel Identifiers are both UUIDs); UserAgent strings can contain high variance to the point that reducing them does not provide a great deal of information; Subscription providers can come from anywhere on the internet; etc.) This greatly limits the amount of detailed information that we can capture.

The following is somewhat speculative, but is drawn from historic and system knowledge.

What I believe to have happened was that Bravoendpoint saw a significant increase in traffic of subscription updates starting at about 08:29 to endpoints that were previously or are currently valid. While this coincides with growth in Bravo command attempts it it not possible to for me to say if this was the cause or just part of the overall wave of traffic.   
The graph of Bravo Pushes attempted, succeeded and failed.
The autoendpoint nodes then started to fail due to OOM, it is not understood what caused this error. Since the endpoints were valid AutoEndpoint then attempted to look up routing information for the appropriate node, which lead to a dramatic increase in Active Connections.  

In addition, a number of these appear to have failed to return information, which would have resulted in a 500 class error:  

This could have caused the Sender to immediately retry sending the Notification, which could have caused new Bravoendpoint nodes to fail due to limited memory. (I have no idea why this could be but perhaps traffic was being buffered by the node as the Bravoendpoint application was starting up?)  
This lead to a cascade problem forcing the number of Bravoendpoint nodes to drop far below it's threshold.  

Changes in the core configurations appear to have helped resolve some of these problems, likewise the wave of incoming requests appears to have also subsided. 

Not sure how related this might be, but there was also a growth in Invalid App\_Ids starting around the same time as the incident began.   

These are generated by "mobile" [registration requests](https://example.com/mozilla-services/bravoservice-rs/blob/master/docs/src/http.md). The `appid` must match a set of known AppIds for the given provider (in this case FCM). Bravoendpoint rejects any registration request that does not have a known AppId, and this should not increase memory or cause Bigtable lookups. It may, however, indicate incoming shenanigans. We might want to block IPs that trigger `Invalid_Appid` errors, but there's some discussion about how to best indicate that to the WAF.

24 hours later, Bravoendpoint's memory usage remains unusually high.The current allocation for autoendpoint is   

[A WAF rule was added](https://example.com/mozilla/webservices-infra/pull/9756/changes) to block any site that generates a high level of security events. 

2025-02-26  
ServiceCloud informed us that our Redis service also had problems. Notably, there were memory errors because we were running low on key space and triggering `maxmemory-gb` errors. That indicates that we were getting a high number of messages from Bravo, since we only use redis to track states for messages we know come from Bravo. The reliability work is not critical, and mostly supplemental, so any outages were not a concern. That said, [we should monitor](https://example.com/browse/PUSH-647) these servers. In addition, I am talking with [Nate](mailto:nate@example.com)about ways to optimize the redis system. 

Notified @sandeep that the BravoService WAF is incorrectly flagging `Content-Type: aes(128)?gcm`. Need to allow the data because it's binary/encrypted. [Work is in progress](https://example.com/mozilla/webservices-infra/pull/9843) to add exceptions for those content types.

2026-02-27  
[Dan](mailto:dan@example.com) dug around in the [Bravo Prod Bigquery data](https://example.com/bigquery) using the following query:  
\`\`\`  
`(SELECT`  
 `window_start,`  
 `-- request_client_ip,`  
 `MAX(COUNT) as MAX,`  
 `AVG(COUNT) as AVG`  
 `FROM (`  
   `SELECT`  
     ``TIMESTAMP_SECONDS(60*15 * DIV(UNIX_SECONDS(`timestamp`), 60*15)) AS window_start,``  
     `request_client_ip,`  
     `COUNT(url) AS count`  
   `` FROM `moz-tenant.bravo_api_accounts_prod_prod_logs.cdn` ``  
   `WHERE`  
     `url LIKE '%devices/notify%'`  
     ``AND `timestamp` >= TIMESTAMP('2026-02-24')``  
     ``AND `timestamp` <  TIMESTAMP('2026-02-25')``  
   `GROUP BY window_start, request_client_ip`  
 `)`  
 `-- WHERE`  
 `--  count > 0 -- Toggle to see impact of potential rate-limiting rule`  
 `GROUP BY`  
   `window_start`  
   `-- , request_client_ip`  
`)`

and determined that there was a spike of requests on the day of the incident and a spike in the max per IP, indicating that a relatively small number of IPs are generating a lot of the traffic. [***Analysis sheet***](https://example.com/spreadsheets/d/sheet2/edit)

# Postmortem Action Items

*\<What are we going to do to prevent recurrence of this issue in our domain, prevent potentially similar issues this incident+postmortem has made us realize are risks, and/or help others in Mozilla prevent these types of issues; this should include tangible actions resulting from things like “lessons learned”; this should include links to jira tickets which are filed for every postmortem action item. **This section is not complete (thus the postmortem is not ‘done’) until jira tickets have been created with ETAs (tentative dates are ok), linked to the ticket for this incident, and listed in the table below.***  
[*See the documentation.*](https://example.com/wiki/spaces/MIR/pages/1891074056/Incident+reports)  
*/\>*

| Jira Ticket \+ Status | Ticket Title / Context / Summary / Reason |
| :---- | :---- |
| \[[PUSH-630](https://example.com/browse/PUSH-630)\] Status: Not started | *20260224-Incident Response Tickets* |
| [https://example.com/browse/INFRASEC-2653](https://example.com/browse/INFRASEC-2653)  | Fastly WAF \- BravoService Incident  Security Engineering ticket |
|  |  |

# \[optional\] Postmortem discussion notes

*\<Anything we want to capture as notes during postmortem discussion. This could be a place to capture notes (who said/shared what, etc). However this is not a place where any form of follow-up or action items go. Instead, those should go into the Postmortem Action Items section. Notice this postmortem doc doesn’t have a “lessons learned” section (or other similar ones), that too goes into Postmortem Action items (if it’s not worth taking specific steps to improve, then it arguably wasn’t a “lesson learned”). The best version of this section is when it is left blank because all the postmortem discussion focused on ensuring the previous sections were correct, and resulted in Postmortem Action Items which helped prevent recurrence of this issue and ones like it across as much of the company as possible.\>*

* Why wasn't dev/SRE alerted via PagerDuty for the Push outage?

# \[optional\] Appendix:

*\<Any additional information that may be of use. For example:*

* *Architecture about your service, to help provide context for the reader*  
* *Captured output*  
* *sampled error*  
* *etc.*

*/\>*  


[^1]:  **Incident Commanders** lead and manage the response to an incident. **Incident Managers** oversee broader incident management processes focusing on strategic planning and resource allocation. See expanded definition [here](https://example.com/wiki/spaces/MIR/pages/20512894/Incident+Severity+Levels).
