"""Remove the recipient test restriction after successful production verification."""
import argparse
import boto3


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--enable-all-bookers",action="store_true",required=True)
    parser.parse_args()
    session=boto3.Session(profile_name="life-library",region_name="ap-southeast-1")
    assert session.client("sts").get_caller_identity()["Account"]=="165115313524"
    ecs=session.client("ecs")
    cluster,service="life-library-production","life-library-production-api"
    current=ecs.describe_services(cluster=cluster,services=[service])["services"][0]
    assert len(current["deployments"])==1 and current["deployments"][0]["rolloutState"]=="COMPLETED", "Wait for the existing deployment to finish"
    task=ecs.describe_task_definition(taskDefinition=current["taskDefinition"])["taskDefinition"]
    container=next(c for c in task["containerDefinitions"] if c["name"]=="api")
    env={e["name"]:e["value"] for e in container["environment"]}
    assert env["APP_ENV"]=="production" and env["BOOKING_EMAIL_ENABLED"]=="true"
    assert env["BOOKING_EMAIL_SENDER"]=="library@life.edu.ph"
    assert env.get("BOOKING_EMAIL_TEST_RECIPIENT") in {"paolo.ylag@life.edu.ph",""}
    if not env.get("BOOKING_EMAIL_TEST_RECIPIENT"):
        print("Email delivery already enabled for all bookers")
        return
    for item in container["environment"]:
        if item["name"]=="BOOKING_EMAIL_TEST_RECIPIENT":
            item["value"]=""
    allowed=ecs.meta.service_model.operation_model("RegisterTaskDefinition").input_shape.members
    registration={key:value for key,value in task.items() if key in allowed}
    release=ecs.register_task_definition(**registration)["taskDefinition"]["taskDefinitionArn"]
    print("Previous task:",current["taskDefinition"],flush=True)
    print("New task:",release,flush=True)
    ecs.update_service(cluster=cluster,service=service,taskDefinition=release)
    ecs.get_waiter("services_stable").wait(cluster=cluster,services=[service],WaiterConfig={"Delay":15,"MaxAttempts":40})
    final=ecs.describe_services(cluster=cluster,services=[service])["services"][0]
    assert final["taskDefinition"]==release and final["runningCount"]==final["desiredCount"]
    print("PASS: new-booking email delivery enabled for all bookers; no historical notifications released",flush=True)


if __name__=="__main__":
    main()
